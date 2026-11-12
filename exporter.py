"""WiGLE / wdgwars.pl compatible CSV export (WigleWifi-1.4) with crash-safe journal."""

from __future__ import annotations

import csv
import json
import os
import platform
import re
import socket
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from . import APP_NAME, __version__
from .models import Observation

COLUMNS = [
    "MAC",
    "SSID",
    "AuthMode",
    "FirstSeen",
    "Channel",
    "RSSI",
    "CurrentLatitude",
    "CurrentLongitude",
    "AltitudeMeters",
    "AccuracyMeters",
    "Type",
]
JOURNAL_PREFIX = ".spejari_"
JOURNAL_SUFFIX = ".journal"


def export_filename(started: datetime) -> str:
    """Spejari_YYYY-MM-DD_HH-MM-SS.csv  (the extension is always lowercase)"""
    return f"{APP_NAME}_{started:%Y-%m-%d_%H-%M-%S}.csv"


def normalize_csv_path(path: Path) -> Path:
    """Force a lowercase '.csv' extension (never '.CSV'); add it if missing."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return path.with_suffix(".csv")
    return path.with_name(path.name + ".csv")


def _clean(text: str) -> str:
    return re.sub(r"[\r\n,]+", " ", text).strip()


def device_info() -> dict:
    model = ""
    for path in ("/proc/device-tree/model", "/sys/devices/virtual/dmi/id/product_name"):
        try:
            with open(path, "rb") as fh:
                model = fh.read().decode("utf-8", "ignore").replace("\x00", "").strip()
        except OSError:
            continue
        if model:
            break
    return {
        "model": _clean(model or platform.machine() or "linux"),
        "release": _clean(platform.release()),
        "device": _clean(socket.gethostname()),
        "board": _clean(platform.machine()),
    }


def wigle_preheader() -> str:
    info = device_info()
    return (
        f"WigleWifi-1.4,appRelease={APP_NAME} {__version__},model={info['model']},"
        f"release={info['release']},device={info['device']},display=,"
        f"board={info['board']},brand={APP_NAME}"
    )


def _chown_to_sudo_user(path: Path) -> None:
    """Hand files created under sudo back to the invoking user."""
    uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if uid and gid:
        try:
            os.chown(path, int(uid), int(gid))
        except OSError:
            pass


def write_wigle_csv(observations: Iterable[Observation], path: Path) -> int:
    """Write observations as WiGLE CSV. Returns the number of data rows."""
    path = normalize_csv_path(path)
    rows = sorted(observations, key=lambda o: (o.seen_utc, o.bssid))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        fh.write(wigle_preheader() + "\n")
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(COLUMNS)
        for o in rows:
            writer.writerow(
                [
                    o.bssid,
                    re.sub(r"[\r\n]+", " ", o.ssid),
                    o.auth,
                    o.seen_utc.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    o.channel,
                    o.rssi,
                    f"{o.lat:.8f}",
                    f"{o.lon:.8f}",
                    f"{o.alt:.1f}",
                    f"{o.accuracy:.1f}",
                    "WIFI",
                ]
            )
    os.replace(tmp, path)
    _chown_to_sudo_user(path)
    return len(rows)


class Journal:
    """Append-only JSON-lines log so a crash or power loss never loses a drive."""

    def __init__(self, directory: Path, started: datetime) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{JOURNAL_PREFIX}{started:%Y-%m-%d_%H-%M-%S}{JOURNAL_SUFFIX}"
        self._fh = open(self.path, "a", encoding="utf-8")
        self._lock = threading.Lock()
        _chown_to_sudo_user(self.path)

    def write(self, obs: Observation) -> None:
        line = json.dumps(obs.to_json(), separators=(",", ":"))
        with self._lock:
            self._fh.write(line + "\n")
            self._fh.flush()

    def close(self) -> None:
        with self._lock:
            if not self._fh.closed:
                self._fh.close()

    def discard(self) -> None:
        self.close()
        try:
            self.path.unlink()
        except OSError:
            pass


def read_journal(path: Path) -> List[Observation]:
    out: List[Observation] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(Observation.from_json(json.loads(line)))
            except (ValueError, KeyError):
                continue  # a torn last line after a power cut
    return out


def recover_journals(directory: Path) -> List[Path]:
    """Convert leftover journals (from crashed sessions) into CSV files."""
    results: List[Path] = []
    for jpath in sorted(directory.glob(f"{JOURNAL_PREFIX}*{JOURNAL_SUFFIX}")):
        stamp = jpath.name[len(JOURNAL_PREFIX) : -len(JOURNAL_SUFFIX)]
        observations = read_journal(jpath)
        if not observations:
            jpath.unlink(missing_ok=True)
            continue
        target = directory / f"{APP_NAME}_{stamp}.csv"
        if target.exists():
            target = directory / f"{APP_NAME}_{stamp}_recovered.csv"
        write_wigle_csv(observations, target)
        jpath.unlink(missing_ok=True)
        results.append(target)
    return results
