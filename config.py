"""Configuration loading for Spejari (TOML file + CLI overrides)."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python < 3.11 needs the "tomli" backport
    import tomli as tomllib

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "spejari.toml"
HARD_MAX_ADAPTERS = 10


class ConfigError(Exception):
    """Raised for unreadable or invalid configuration files."""


@dataclass
class ScanConfig:
    max_adapters: int = HARD_MAX_ADAPTERS  # hard limit is 10
    include_interfaces: List[str] = field(default_factory=list)
    exclude_interfaces: List[str] = field(default_factory=list)
    band_2g: bool = True
    band_5g: bool = True
    skip_dfs: bool = False
    exclude_channels: List[int] = field(default_factory=list)
    passive: bool = False
    channels_per_scan: int = 1
    adapter_poll_interval: float = 2.0
    scan_timeout: float = 20.0


@dataclass
class LogConfig:
    output_dir: str = "exports"
    min_distance_m: float = 25.0
    rssi_improvement_db: int = 8
    feed_update_interval: float = 5.0


@dataclass
class GpsConfig:
    source: str = "auto"  # auto | gpsd | serial | none
    gpsd_host: str = "127.0.0.1"
    gpsd_port: int = 2947
    serial_port: str = ""  # empty = auto-detect
    baud: int = 0  # 0 = auto-detect
    probe_other_ports: bool = False  # also probe non-u-blox serial devices
    min_fix_mode: int = 2  # 2 = accept 2D fixes, 3 = require 3D
    min_step_m: float = 5.0  # ignore GPS jitter below this step
    max_speed_mps: float = 70.0  # reject position jumps implying > 250 km/h
    stale_after_s: float = 5.0


@dataclass
class UiConfig:
    default_mode: str = "ask"  # ask | cli | gui
    refresh_hz: float = 4.0
    feed_history: int = 500


@dataclass
class Config:
    scan: ScanConfig = field(default_factory=ScanConfig)
    log: LogConfig = field(default_factory=LogConfig)
    gps: GpsConfig = field(default_factory=GpsConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    warnings: List[str] = field(default_factory=list)

    @property
    def output_path(self) -> Path:
        p = Path(self.log.output_dir).expanduser()
        return p if p.is_absolute() else PROJECT_ROOT / p

    def normalise(self) -> None:
        s = self.scan
        s.max_adapters = max(1, min(HARD_MAX_ADAPTERS, int(s.max_adapters)))
        s.channels_per_scan = max(1, min(8, int(s.channels_per_scan)))
        s.adapter_poll_interval = max(0.5, float(s.adapter_poll_interval))
        s.exclude_channels = [int(c) for c in s.exclude_channels]
        self.gps.source = str(self.gps.source).lower()
        if self.gps.source not in ("auto", "gpsd", "serial", "none"):
            self.warnings.append(f"Unknown gps.source '{self.gps.source}', using 'auto'")
            self.gps.source = "auto"
        self.gps.min_fix_mode = 3 if int(self.gps.min_fix_mode) >= 3 else 2
        self.ui.refresh_hz = max(1.0, min(20.0, float(self.ui.refresh_hz)))
        self.ui.default_mode = str(self.ui.default_mode).lower()
        if self.ui.default_mode not in ("ask", "cli", "gui"):
            self.warnings.append(f"Unknown ui.default_mode '{self.ui.default_mode}', using 'ask'")
            self.ui.default_mode = "ask"


def _apply(section: Any, data: Dict[str, Any], name: str, warnings: List[str]) -> None:
    valid = {f.name for f in fields(section)}
    for key, value in data.items():
        if key in valid:
            setattr(section, key, value)
        else:
            warnings.append(f"Unknown option [{name}] {key}")


def load_config(path: Optional[str] = None) -> Config:
    """Load configuration. An explicit *path* must exist; the default may be absent."""
    cfg = Config()
    target = Path(path).expanduser() if path else DEFAULT_CONFIG_PATH
    if target.is_file():
        try:
            with open(target, "rb") as fh:
                data = tomllib.load(fh)
        except (OSError, ValueError) as exc:
            raise ConfigError(f"Cannot read config {target}: {exc}") from exc
        for name in ("scan", "log", "gps", "ui"):
            section = data.get(name)
            if isinstance(section, dict):
                _apply(getattr(cfg, name), section, name, cfg.warnings)
        for key in data:
            if key not in ("scan", "log", "gps", "ui"):
                cfg.warnings.append(f"Unknown config section [{key}]")
    elif path:
        raise ConfigError(f"Config file not found: {target}")
    cfg.normalise()
    return cfg
