"""A scanning session: de-duplication, logging policy and live statistics."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from .config import Config
from .geo import haversine_m
from .models import AccessPoint, FeedEntry, FeedLog, GpsFix, Observation


@dataclass
class Network:
    bssid: str
    ssid: str
    channel: int
    rssi: int
    hits: int = 0
    logged: int = 0
    best_logged_rssi: int = -200
    last_logged_pos: Optional[Tuple[float, float]] = None
    last_feed: float = 0.0


@dataclass
class SessionStats:
    unique_ssids: int
    unique_bssids: int
    hidden: int
    logged: int
    seen_no_fix: int
    hits: int


class Session:
    """Collects access points seen by all adapters during one start/stop cycle.

    Every distinct BSSID is logged on first sight (when GPS has a fix). It is
    logged again when the receiver has moved ``min_distance_m`` since its last
    logged position or when the signal improved by ``rssi_improvement_db`` -
    this gives WiGLE-style services enough data to triangulate each network
    without writing a row for every beacon.
    """

    def __init__(self, cfg: Config, feed: FeedLog, journal=None) -> None:
        self.cfg = cfg
        self.feed = feed
        self.journal = journal
        self.started_local = datetime.now()
        self.started_mono = time.monotonic()
        self.distance_baseline_m = 0.0
        self.observations: List[Observation] = []
        self._networks: Dict[str, Network] = {}
        self._ssids: Set[str] = set()
        self._hits = 0
        self._no_fix = 0
        self._lock = threading.Lock()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started_mono

    def stats(self) -> SessionStats:
        with self._lock:
            return SessionStats(
                unique_ssids=len(self._ssids),
                unique_bssids=len(self._networks),
                hidden=sum(1 for n in self._networks.values() if n.ssid == ""),
                logged=len(self.observations),
                seen_no_fix=self._no_fix,
                hits=self._hits,
            )

    def ingest_batch(self, aps: List[AccessPoint], adapter: str, fix: GpsFix, now_utc: datetime) -> None:
        with self._lock:
            for ap in aps:
                self._ingest(ap, adapter, fix, now_utc)

    # -- internals (lock held) -----------------------------------------------
    def _ingest(self, ap: AccessPoint, adapter: str, fix: GpsFix, now_utc: datetime) -> None:
        net = self._networks.get(ap.bssid)
        is_new = net is None
        if net is None:
            net = Network(ap.bssid, ap.ssid, ap.channel, ap.rssi)
            self._networks[ap.bssid] = net
            if ap.ssid:
                self._ssids.add(ap.ssid)
        elif ap.ssid and not net.ssid:  # hidden network revealed by a probe response
            net.ssid = ap.ssid
            self._ssids.add(ap.ssid)
        net.hits += 1
        net.rssi, net.channel = ap.rssi, ap.channel
        self._hits += 1

        if self._should_log(net, ap, fix):
            self._log(net, ap, fix, now_utc)
        elif not fix.valid:
            self._no_fix += 1

        now = time.monotonic()
        if is_new or now - net.last_feed >= self.cfg.log.feed_update_interval:
            net.last_feed = now
            self.feed.add(
                FeedEntry(
                    ts=time.time(),
                    kind="NEW" if is_new else "UPD",
                    ssid=net.ssid,
                    bssid=ap.bssid,
                    channel=ap.channel,
                    band=ap.band,
                    rssi=ap.rssi,
                    security=ap.security,
                    adapter=adapter,
                )
            )

    def _should_log(self, net: Network, ap: AccessPoint, fix: GpsFix) -> bool:
        if not fix.valid or fix.lat is None or fix.lon is None:
            return False
        if net.logged == 0 or net.last_logged_pos is None:
            return True
        moved = haversine_m(net.last_logged_pos[0], net.last_logged_pos[1], fix.lat, fix.lon)
        if moved >= self.cfg.log.min_distance_m:
            return True
        return ap.rssi >= net.best_logged_rssi + self.cfg.log.rssi_improvement_db

    def _log(self, net: Network, ap: AccessPoint, fix: GpsFix, now_utc: datetime) -> None:
        obs = Observation(
            bssid=ap.bssid,
            ssid=net.ssid or ap.ssid,
            auth=ap.auth,
            seen_utc=now_utc,
            channel=ap.channel,
            rssi=ap.rssi,
            lat=float(fix.lat),
            lon=float(fix.lon),
            alt=float(fix.alt) if fix.alt is not None else 0.0,
            accuracy=float(fix.accuracy_m) if fix.accuracy_m is not None else 0.0,
        )
        self.observations.append(obs)
        net.logged += 1
        net.last_logged_pos = (obs.lat, obs.lon)
        net.best_logged_rssi = max(net.best_logged_rssi, ap.rssi)
        if self.journal is not None:
            self.journal.write(obs)
