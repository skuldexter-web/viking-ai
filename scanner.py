"""Scanning engine: per-adapter workers, dynamic clustering and hot-plug re-balancing."""

from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

from .adapters import Adapter, AdapterDetector, AdapterError, natural_key, run_cmd
from .channels import distribute
from .config import Config
from .gps import GpsMonitor
from .models import AdapterView, FeedLog
from .parser import parse_iw_scan
from .session import Session


class ScanError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind  # busy | gone | down | perm | timeout | other


def run_scan(ifname: str, freqs: List[int], passive: bool, timeout: float) -> str:
    """Trigger one scan on specific frequencies and return the iw output."""
    cmd = ["iw", "dev", ifname, "scan", "flush", "freq", *[str(f) for f in freqs]]
    if passive:
        cmd.append("passive")
    rc, out, err = run_cmd(cmd, timeout=timeout)
    if rc == 0:
        return out
    msg = (err or out).strip()
    low = msg.lower()
    if rc == 124:
        raise ScanError("timeout", "scan timed out")
    if "busy" in low or "(-16)" in msg:
        raise ScanError("busy", msg)
    if "no such device" in low or "(-19)" in msg:
        raise ScanError("gone", msg)
    if "network is down" in low or "(-100)" in msg:
        raise ScanError("down", msg)
    if "not permitted" in low or "(-1)" in msg:
        raise ScanError("perm", msg)
    raise ScanError("other", msg)


class AdapterWorker(threading.Thread):
    """Scans the channels assigned to one adapter, round-robin."""

    MAX_ERRORS = 8

    def __init__(self, engine: "ScanEngine", adapter: Adapter) -> None:
        super().__init__(name=f"spejari-scan-{adapter.ifname}", daemon=True)
        self.engine = engine
        self.adapter = adapter
        self.ifname = adapter.ifname
        self._stop_evt = threading.Event()
        self._cursor = 0
        self._errors = 0
        self._last_warn = 0.0
        self.unhealthy_until = 0.0
        self.busy = False
        self.current: List[int] = []
        self.state = "starting"
        self.hits = 0

    # -- control ---------------------------------------------------------------
    def stop(self) -> None:
        self._stop_evt.set()

    @property
    def healthy(self) -> bool:
        return time.monotonic() >= self.unhealthy_until

    def _warn(self, text: str) -> None:
        now = time.monotonic()
        if now - self._last_warn > 30:
            self._last_warn = now
            self.engine.feed.system(f"{self.ifname}: {text}", warn=True)

    def _next_batch(self, freqs: List[int]) -> List[int]:
        n = self.engine.cfg.scan.channels_per_scan
        batch = [freqs[(self._cursor + i) % len(freqs)] for i in range(min(n, len(freqs)))]
        self._cursor = (self._cursor + n) % len(freqs)
        return batch

    # -- main loop -------------------------------------------------------------
    def run(self) -> None:
        run_cmd(["ip", "link", "set", "dev", self.ifname, "up"], timeout=5)
        scan_cfg = self.engine.cfg.scan
        while not self._stop_evt.is_set():
            if not self.engine.scanning.is_set():
                self.state, self.current = "idle", []
                self._stop_evt.wait(0.3)
                continue
            freqs = self.engine.channels_for(self.ifname)
            if not freqs:
                self.state, self.current = "no channels", []
                self._stop_evt.wait(0.5)
                continue
            batch = self._next_batch(freqs)
            self.current, self.state = batch, "scanning"
            self.busy = True
            try:
                out = run_scan(self.ifname, batch, scan_cfg.passive, scan_cfg.scan_timeout)
                aps = parse_iw_scan(out)
                self._errors = 0
                self.hits += len(aps)
                if aps:
                    self.engine.ingest_batch(aps, self.ifname)
            except ScanError as exc:
                if self._handle_error(exc):
                    return
            finally:
                self.busy = False

    def _handle_error(self, exc: ScanError) -> bool:
        """Returns True when the worker should terminate."""
        kind = str(exc.kind)
        if kind == "gone":
            self.state = "removed"
            return True
        if kind == "busy":
            self.state = "busy"
            self._stop_evt.wait(0.4)
            return False
        if kind == "down":
            run_cmd(["ip", "link", "set", "dev", self.ifname, "up"], timeout=5)
            self._stop_evt.wait(1.0)
            return False
        if kind == "perm":
            self.state = "no permission"
            self._warn("scan not permitted - run Spejari as root (sudo)")
            self.unhealthy_until = time.monotonic() + 15
            self._stop_evt.wait(15)
            return False
        self._errors += 1
        self.state = "error"
        self._warn(f"scan failed: {str(exc)[:80]}")
        if self._errors >= self.MAX_ERRORS:
            self._errors = 0
            self.unhealthy_until = time.monotonic() + 15
            self._stop_evt.wait(15)
        else:
            self._stop_evt.wait(min(0.5 * self._errors, 4.0))
        return False


class ScanEngine:
    """Detects adapters, balances channels across them and runs the workers."""

    def __init__(self, cfg: Config, gps: GpsMonitor, feed: FeedLog) -> None:
        self.cfg = cfg
        self.gps = gps
        self.feed = feed
        self.detector = AdapterDetector(cfg.scan)
        self.scanning = threading.Event()
        self.session: Optional[Session] = None
        self.detect_error: Optional[str] = None
        self._lock = threading.RLock()
        self._stop_evt = threading.Event()
        self._workers: Dict[str, AdapterWorker] = {}
        self._adapters: Dict[str, Adapter] = {}
        self._skipped: List[Dict[str, str]] = []
        self._plan: Dict[str, List[int]] = {}
        self._plan_sig: Optional[tuple] = None
        self._last_error_msg = ""
        self._warned_truncated = False
        self._manager = threading.Thread(target=self._manage, name="spejari-cluster", daemon=True)

    # -- lifecycle -------------------------------------------------------------
    def start(self) -> None:
        self._manager.start()

    def shutdown(self) -> None:
        self._stop_evt.set()
        self.scanning.clear()
        with self._lock:
            workers = list(self._workers.values())
        for w in workers:
            w.stop()
        for w in workers:
            w.join(timeout=3.0)

    def begin_session(self, session: Session) -> None:
        with self._lock:
            self.session = session
        self.scanning.set()

    def end_session(self, timeout: float = 20.0) -> Optional[Session]:
        """Stop scanning, let in-flight scans finish, detach and return the session."""
        self.scanning.clear()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if not any(w.busy for w in self._workers.values()):
                    break
            time.sleep(0.1)
        with self._lock:
            session, self.session = self.session, None
        return session

    # -- data flow -------------------------------------------------------------
    def channels_for(self, ifname: str) -> List[int]:
        with self._lock:
            return list(self._plan.get(ifname, []))

    def ingest_batch(self, aps, ifname: str) -> None:
        session = self.session
        if session is None:
            return
        session.ingest_batch(aps, ifname, self.gps.snapshot(), self.gps.utc_now())

    def skipped_adapters(self) -> List[Dict[str, str]]:
        with self._lock:
            return list(self._skipped)

    def adapter_count(self) -> int:
        with self._lock:
            return len(self._adapters)

    def adapter_views(self) -> List[AdapterView]:
        with self._lock:
            views = []
            for name in sorted(self._adapters, key=natural_key):
                a, w = self._adapters[name], self._workers.get(name)
                views.append(
                    AdapterView(
                        ifname=name,
                        driver=a.driver,
                        phy=a.phy,
                        channels=list(self._plan.get(name, [])),
                        current=list(w.current) if w else [],
                        state=w.state if w else "starting",
                        hits=w.hits if w else 0,
                    )
                )
            return views

    # -- cluster manager (hot-plug aware) --------------------------------------
    def _manage(self) -> None:
        while not self._stop_evt.is_set():
            try:
                adapters = self.detector.detect()
                self.detect_error = None
            except AdapterError as exc:
                adapters, self.detect_error = [], str(exc)
                if str(exc) != self._last_error_msg:
                    self._last_error_msg = str(exc)
                    self.feed.system(str(exc), warn=True)
            if self.detector.truncated and not self._warned_truncated:
                self._warned_truncated = True
                self.feed.system(
                    f"{self.detector.truncated} extra adapter(s) ignored (limit {self.cfg.scan.max_adapters})",
                    warn=True,
                )
            with self._lock:
                self._skipped = list(self.detector.skipped)
            self._apply(adapters)
            self._stop_evt.wait(self.cfg.scan.adapter_poll_interval)

    def _apply(self, adapters: List[Adapter]) -> None:
        new = {a.ifname: a for a in adapters}
        with self._lock:
            old_names = set(self._adapters)
            for name in old_names - set(new):
                worker = self._workers.pop(name, None)
                if worker:
                    worker.stop()
                self.feed.system(f"Adapter {name} removed")
            for name, adapter in new.items():
                worker = self._workers.get(name)
                if worker is None or not worker.is_alive():
                    if name in old_names and worker is not None:
                        self.feed.system(f"Restarting scanner on {name}", warn=True)
                    worker = AdapterWorker(self, adapter)
                    self._workers[name] = worker
                    worker.start()
                    if name not in old_names:
                        self.feed.system(f"Adapter {name} ({adapter.driver}) added")
            self._adapters = new

            healthy = {n: a.channels for n, a in new.items() if self._workers[n].healthy}
            signature = tuple(sorted((n, tuple(c)) for n, c in healthy.items()))
            if signature != self._plan_sig:
                first = self._plan_sig is None
                self._plan = distribute(healthy)
                self._plan_sig = signature
                if self._plan and not (first and not old_names and not new):
                    total = len({f for chans in healthy.values() for f in chans})
                    parts = " | ".join(
                        f"{n}: {len(c)} ch" for n, c in sorted(self._plan.items())
                    )
                    self.feed.system(
                        f"Channel plan: {len(self._plan)} adapter(s), {total} channels  [{parts}]"
                    )
                elif not self._plan and old_names:
                    self.feed.system("No usable adapters - waiting for hot-plug", warn=True)
