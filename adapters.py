"""Wireless adapter discovery (via `iw`) and capability parsing."""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .channels import in_scope, select_channels


def natural_key(name: str):
    """Sort wlan2 before wlan10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


class AdapterError(Exception):
    pass


class ToolMissing(AdapterError):
    pass


@dataclass
class Adapter:
    ifname: str
    phy: str
    mac: str
    driver: str
    channels: List[int] = field(default_factory=list)  # usable frequencies (MHz)


def run_cmd(args: List[str], timeout: float = 10.0) -> Tuple[int, str, str]:
    env = dict(os.environ, LC_ALL="C")
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, errors="replace", timeout=timeout, env=env
        )
    except FileNotFoundError as exc:
        raise ToolMissing(f"'{args[0]}' not found - install it (sudo apt install iw)") from exc
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    return proc.returncode, proc.stdout, proc.stderr


def parse_iw_dev(text: str) -> List[Dict[str, str]]:
    """Parse `iw dev` into a list of {ifname, phy, type, addr} dicts."""
    out: List[Dict[str, str]] = []
    phy = ""
    cur: Optional[Dict[str, str]] = None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"phy#(\d+)", line)
        if m:
            phy, cur = f"phy{m.group(1)}", None
            continue
        if line.startswith("Unnamed/non-netdev"):
            cur = None
            continue
        m = re.match(r"Interface\s+(\S+)", line)
        if m:
            cur = {"ifname": m.group(1), "phy": phy, "type": "", "addr": ""}
            out.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("type "):
            cur["type"] = line.split(None, 1)[1].strip()
        elif line.startswith("addr "):
            cur["addr"] = line.split(None, 1)[1].strip()
    return out


_FREQ_LINE = re.compile(r"^\s*\*\s*(\d+)(?:\.\d+)?\s+MHz\s+\[(\d+)\](.*)$")


def parse_phy_freqs(text: str) -> List[int]:
    """Parse `iw phy <phy> info` into the list of enabled 2.4/5 GHz frequencies."""
    freqs: List[int] = []
    for line in text.splitlines():
        m = _FREQ_LINE.match(line)
        if not m:
            continue
        freq = int(m.group(1))
        if "disabled" in m.group(3):
            continue
        if in_scope(freq):
            freqs.append(freq)
    return sorted(set(freqs))


def driver_of(ifname: str) -> str:
    try:
        return os.path.basename(os.path.realpath(f"/sys/class/net/{ifname}/device/driver")) or "?"
    except OSError:
        return "?"


class AdapterDetector:
    """Finds scan-capable adapters and caches per-PHY channel capabilities."""

    PHY_CACHE_TTL = 300.0

    def __init__(self, scan_cfg) -> None:
        self.cfg = scan_cfg
        self.truncated = 0  # adapters ignored because of the max_adapters limit
        self.skipped: List[Dict[str, str]] = []  # detected but unused: {ifname, driver, reason}
        self._phy_cache: Dict[str, Tuple[float, List[int]]] = {}

    def _phy_freqs(self, phy: str) -> List[int]:
        now = time.monotonic()
        cached = self._phy_cache.get(phy)
        if cached and now - cached[0] < self.PHY_CACHE_TTL:
            return cached[1]
        rc, out, err = run_cmd(["iw", "phy", phy, "info"])
        if rc != 0:
            raise AdapterError(f"iw phy {phy} info failed: {err.strip()}")
        freqs = parse_phy_freqs(out)
        self._phy_cache[phy] = (now, freqs)
        return freqs

    def detect(self) -> List[Adapter]:
        rc, out, err = run_cmd(["iw", "dev"])
        if rc != 0:
            raise AdapterError(f"iw dev failed: {err.strip() or out.strip()}")
        found: List[Adapter] = []
        seen_phys = set()
        self.truncated = 0
        skipped: List[Dict[str, str]] = []
        for item in sorted(parse_iw_dev(out), key=lambda i: natural_key(i["ifname"])):
            name = item["ifname"]
            if item["type"] != "managed":
                continue
            if self.cfg.include_interfaces and name not in self.cfg.include_interfaces:
                skipped.append({"ifname": name, "driver": driver_of(name), "reason": "not selected"})
                continue
            if name in self.cfg.exclude_interfaces:
                skipped.append({"ifname": name, "driver": driver_of(name), "reason": "excluded"})
                continue
            if item["phy"] in seen_phys:  # several virtual ifaces on one radio
                continue
            try:
                chans = select_channels(self._phy_freqs(item["phy"]), self.cfg)
            except AdapterError:
                continue
            if not chans:
                continue
            if len(found) >= self.cfg.max_adapters:
                self.truncated += 1
                skipped.append({"ifname": name, "driver": driver_of(name), "reason": "over limit"})
                continue
            seen_phys.add(item["phy"])
            found.append(
                Adapter(name, item["phy"], item["addr"], driver_of(name), chans)
            )
        self.skipped = skipped
        live = {a.phy for a in found}
        for phy in list(self._phy_cache):
            if phy not in live:
                del self._phy_cache[phy]
        return found
