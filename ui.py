"""Rich-based live dashboard and keyboard handling."""

from __future__ import annotations

import os
import select
import sys
import termios
import tty
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from rich import box
from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__
from .channels import describe_channels, freq_to_channel
from .models import AdapterView, FeedEntry, GpsFix

BANNER = "\n".join(
    [
        "╔═╗╔═╗╔═╗ ╦╔═╗╦═╗╦",
        "╚═╗╠═╝║╣  ║╠═╣╠╦╝║",
        "╚═╝╩  ╚═╝╚╝╩ ╩╩╚═╩",
    ]
)
TAGLINE = "ᛋ  scout of the 2.4 / 5 GHz airwaves  ᛋ"

BORDER = "steel_blue1"
ACCENT = "gold1"


def print_banner(console: Console) -> None:
    console.print(Text(BANNER, style=f"bold {ACCENT}"))
    console.print(Text(f"{TAGLINE}   v{__version__}", style="steel_blue1"))
    console.print()


@dataclass
class DashboardView:
    state: str = "IDLE"  # IDLE | RUNNING | STOPPING
    elapsed_s: float = 0.0
    unique_ssids: int = 0
    unique_bssids: int = 0
    hidden: int = 0
    logged: int = 0
    seen_no_fix: int = 0
    gps: GpsFix = field(default_factory=GpsFix)
    session_km: float = 0.0
    adapters: List[AdapterView] = field(default_factory=list)
    max_adapters: int = 6
    feed: List[FeedEntry] = field(default_factory=list)
    last_export: str = ""
    utc_now: Optional[datetime] = None


def fmt_duration(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def safe_text(value: str, style: str = "") -> Text:
    """SSIDs are attacker-controlled: never feed them through Rich markup."""
    cleaned = "".join(ch if ch.isprintable() else "·" for ch in value)
    return Text(cleaned, style=style, no_wrap=True, overflow="ellipsis")


def rssi_style(rssi: int) -> str:
    if rssi >= -60:
        return "bold green"
    if rssi >= -75:
        return "yellow"
    return "red"


# ------------------------------------------------------------------------- panels
def _kv_table() -> Table:
    t = Table.grid(padding=(0, 1))
    t.add_column(justify="right", style="bold steel_blue1", no_wrap=True, width=10)
    t.add_column(no_wrap=True, overflow="ellipsis")
    return t


def _gps_style(gps: GpsFix) -> str:
    if gps.valid:
        return "bold green"
    return "yellow" if gps.connected else "red"


def session_panel(v: DashboardView) -> Panel:
    t = _kv_table()
    if v.state == "RUNNING":
        state = Text(f"● SCANNING  {fmt_duration(v.elapsed_s)}", style="bold green")
    elif v.state == "STOPPING":
        state = Text("◌ STOPPING - exporting CSV...", style="bold yellow")
    else:
        state = Text("○ IDLE  (press S to start)", style="bold white")
    t.add_row("Session", state)
    t.add_row("SSIDs", Text(f"{v.unique_ssids}", style=f"bold {ACCENT}"))
    t.add_row("BSSIDs", Text(f"{v.unique_bssids}  (hidden {v.hidden})"))
    logged = f"{v.logged} logged"
    if v.seen_no_fix:
        logged += f" · {v.seen_no_fix} hits w/o fix"
    t.add_row("Logged", logged)

    g = v.gps
    t.add_row("GPS", Text(g.status, style=_gps_style(g)))
    if g.valid and g.lat is not None and g.lon is not None:
        t.add_row("Position", f"{g.lat:+.6f}, {g.lon:+.6f}")
        alt = f"{g.alt:.0f} m" if g.alt is not None else "-"
        spd = f"{g.speed_mps * 3.6:.0f} km/h" if g.speed_mps is not None else "-"
        t.add_row("Alt/Speed", f"{alt} · {spd}")
    else:
        t.add_row("Position", Text("-", style="dim"))
        t.add_row("Alt/Speed", Text("-", style="dim"))
    src = g.device or g.source
    hdop = f" · HDOP {g.hdop:.1f}" if g.hdop is not None else ""
    t.add_row("Source", Text(f"{src}{hdop}" if g.connected else "-", style="dim"))
    t.add_row("Distance", Text(f"{v.session_km:.3f} km", style=f"bold {ACCENT}"))
    t.add_row("Export", Text(v.last_export or "-", style="dim"))
    return Panel(t, title="[bold]Status & Metrics[/]", border_style=BORDER, box=box.ROUNDED)


def adapters_panel(v: DashboardView) -> Panel:
    title = f"[bold]Adapters ({len(v.adapters)}/{v.max_adapters})[/]"
    if not v.adapters:
        msg = Text("No scan-capable wireless adapter detected.\nPlug one in - Spejari hot-plugs.", style="yellow")
        return Panel(msg, title=title, border_style=BORDER, box=box.ROUNDED)
    t = Table(box=None, expand=True, show_header=True, header_style="bold steel_blue1", pad_edge=False, padding=(0, 1))
    t.add_column("Iface", no_wrap=True)
    t.add_column("Driver", no_wrap=True, max_width=10)
    t.add_column("Ch", justify="right", no_wrap=True)
    t.add_column("Assigned channels", ratio=1, no_wrap=True, overflow="ellipsis")
    t.add_column("Now", no_wrap=True, justify="right")
    t.add_column("Hits", justify="right", no_wrap=True)
    t.add_column("State", no_wrap=True)
    for a in v.adapters:
        now = ",".join(str(freq_to_channel(f)) for f in a.current) or "-"
        state_style = "green" if a.state == "scanning" else ("dim" if a.state == "idle" else "yellow")
        t.add_row(
            safe_text(a.ifname, ACCENT),
            safe_text(a.driver),
            str(len(a.channels)),
            safe_text(describe_channels(a.channels)),
            now,
            str(a.hits),
            Text(a.state, style=state_style),
        )
    all_ch = {f for a in v.adapters for f in a.channels}
    total = len(all_ch)
    footer = Text(
        f"Cluster: {len(v.adapters)} adapter(s) share {total} channels "
        f"({' / '.join(str(len(a.channels)) for a in v.adapters)})",
        style="dim",
    )
    return Panel(Group(t, footer), title=title, border_style=BORDER, box=box.ROUNDED)


class FeedRenderable:
    """Renders as many of the newest feed rows as the region allows."""

    def __init__(self, entries: List[FeedEntry]) -> None:
        self.entries = entries

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        height = options.height or 15
        rows = max(1, height - 1)  # one line for the header
        t = Table(box=None, expand=True, show_header=True, header_style="bold steel_blue1", pad_edge=False, padding=(0, 1))
        t.add_column("Time", no_wrap=True, width=8)
        t.add_column("Evt", no_wrap=True, width=4)
        t.add_column("SSID", ratio=1, no_wrap=True, overflow="ellipsis", min_width=10)
        t.add_column("BSSID", no_wrap=True, width=17)
        t.add_column("Ch", justify="right", no_wrap=True, width=3)
        t.add_column("Band", no_wrap=True, width=4)
        t.add_column("RSSI", justify="right", no_wrap=True, width=4)
        t.add_column("Security", no_wrap=True, width=9)
        t.add_column("Iface", no_wrap=True, width=8, overflow="ellipsis")
        for e in self.entries[-rows:]:
            ts = datetime.fromtimestamp(e.ts).strftime("%H:%M:%S")
            if e.kind in ("SYS", "WARN"):
                style = "cyan" if e.kind == "SYS" else "bold yellow"
                t.add_row(Text(ts, style="dim"), Text(e.kind, style=style), safe_text(e.message, style), "", "", "", "", "", "")
                continue
            new = e.kind == "NEW"
            hidden = e.ssid == ""
            ssid = safe_text("<hidden>" if hidden else e.ssid, "italic dim" if hidden else ("bold" if new else ""))
            t.add_row(
                Text(ts, style="dim"),
                Text(e.kind, style="bold green" if new else "dim"),
                ssid,
                Text(e.bssid, style="dim"),
                str(e.channel),
                f"{e.band}G",
                Text(str(e.rssi), style=rssi_style(e.rssi)),
                safe_text(e.security, "red" if e.security in ("Open", "WEP") else ""),
                safe_text(e.adapter, "dim"),
            )
        yield t


def render_dashboard(v: DashboardView) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=1),
        Layout(name="top", size=max(12, len(v.adapters) + 4)),
        Layout(name="feed"),
        Layout(name="footer", size=1),
    )
    clock = v.utc_now.strftime("%H:%M:%S UTC") if v.utc_now else ""
    header = Text(justify="left", no_wrap=True, overflow="ellipsis")
    header.append(" ᛋ SPEJARI ", style=f"bold black on {ACCENT}")
    header.append(f" v{__version__}  Wi-Fi war-driving · 2.4 / 5 GHz · {clock}", style="steel_blue1")
    layout["header"].update(header)
    layout["top"].split_row(Layout(session_panel(v), ratio=5), Layout(adapters_panel(v), ratio=7))
    layout["feed"].update(
        Panel(FeedRenderable(v.feed), title="[bold]Live Feed[/]", border_style=BORDER, box=box.ROUNDED)
    )
    if v.state == "RUNNING":
        keys = "[S] stop & export CSV   [Q] quit (exports first)"
    elif v.state == "STOPPING":
        keys = "exporting - please wait..."
    else:
        keys = "[S] start session   [Q] quit"
    layout["footer"].update(Text(f" {keys}", style="dim", no_wrap=True, overflow="ellipsis"))
    return layout


# ---------------------------------------------------------------------- keyboard
class KeyReader:
    """Non-blocking single-key reader (cbreak mode); inert when stdin is not a TTY."""

    def __init__(self) -> None:
        self.enabled = sys.stdin.isatty()
        self._old = None

    def __enter__(self) -> "KeyReader":
        if self.enabled:
            self._old = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, *exc) -> None:
        if self.enabled and self._old is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old)

    def read(self, timeout: float) -> List[str]:
        if not self.enabled:
            import time

            time.sleep(timeout)
            return []
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if not ready:
            return []
        data = os.read(sys.stdin.fileno(), 32)
        return list(data.decode("utf-8", errors="ignore").lower())
