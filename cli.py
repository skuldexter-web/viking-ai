"""Command-line entry point."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from typing import List, Optional

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from . import __version__
from .adapters import AdapterDetector, AdapterError
from .channels import distribute, describe_channels, freq_to_band, is_dfs
from .config import ConfigError, load_config
from .exporter import recover_journals
from .gps import candidate_serial_ports, usb_ids
from .ui import print_banner


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spejari",
        description="Spejari - multi-adapter Wi-Fi war-driving scout (2.4 / 5 GHz) with GPS and WiGLE CSV export.",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--cli", action="store_true", help="terminal dashboard (works over SSH)")
    mode.add_argument("--gui", action="store_true", help="desktop window (CustomTkinter)")
    p.add_argument("-c", "--config", help="path to a TOML config file (default: config/spejari.toml)")
    p.add_argument("-i", "--interface", action="append", default=[], metavar="IFACE",
                   help="use only this adapter (repeatable)")
    p.add_argument("-x", "--exclude", action="append", default=[], metavar="IFACE",
                   help="never use this adapter, e.g. the one carrying your SSH link (repeatable)")
    p.add_argument("-n", "--max-adapters", type=int, metavar="N", help="adapter limit (1-10)")
    p.add_argument("-b", "--band", choices=("both", "2.4", "5"), help="restrict scanned bands")
    p.add_argument("--skip-dfs", action="store_true", help="skip 5 GHz DFS/radar channels (52-144)")
    p.add_argument("--passive", action="store_true", help="passive scans only (never send probe requests)")
    p.add_argument("--gps", choices=("auto", "gpsd", "serial", "none"), help="GPS source")
    p.add_argument("--gps-device", metavar="DEV", help="serial GPS device, e.g. /dev/ttyACM0 (implies --gps serial)")
    p.add_argument("--gpsd", metavar="HOST:PORT", help="gpsd address (default 127.0.0.1:2947)")
    p.add_argument("-o", "--output-dir", metavar="DIR", help="where CSV exports are written")
    p.add_argument("--auto-start", action="store_true", help="start scanning immediately")
    p.add_argument("--list-adapters", action="store_true", help="show detected adapters, channel split and GPS devices, then exit")
    p.add_argument("--recover", action="store_true", help="convert journals of crashed sessions into CSV files, then exit")
    p.add_argument("-V", "--version", action="store_true", help="print version and exit")
    return p


def apply_overrides(cfg, args) -> None:
    if args.interface:
        cfg.scan.include_interfaces = list(args.interface)
    if args.exclude:
        cfg.scan.exclude_interfaces = list(cfg.scan.exclude_interfaces) + list(args.exclude)
    if args.max_adapters:
        cfg.scan.max_adapters = args.max_adapters
    if args.band:
        cfg.scan.band_2g = args.band in ("both", "2.4")
        cfg.scan.band_5g = args.band in ("both", "5")
    if args.skip_dfs:
        cfg.scan.skip_dfs = True
    if args.passive:
        cfg.scan.passive = True
    if args.gps:
        cfg.gps.source = args.gps
    if args.gps_device:
        cfg.gps.serial_port = args.gps_device
        if not args.gps:
            cfg.gps.source = "serial"
    if args.gpsd:
        host, _, port = args.gpsd.partition(":")
        cfg.gps.gpsd_host = host or cfg.gps.gpsd_host
        if port.isdigit():
            cfg.gps.gpsd_port = int(port)
    if args.output_dir:
        cfg.log.output_dir = args.output_dir
    cfg.normalise()


def list_adapters(cfg, console: Console) -> int:
    print_banner(console)
    try:
        adapters = AdapterDetector(cfg.scan).detect()
    except AdapterError as exc:
        console.print(f"[red]{exc}[/]")
        return 1
    if not adapters:
        console.print("[yellow]No scan-capable (managed-mode) wireless adapters found.[/]")
    else:
        t = Table(title="Wireless adapters", header_style="bold")
        for col in ("Iface", "PHY", "Driver", "MAC", "2.4 GHz", "5 GHz", "of which DFS"):
            t.add_column(col)
        for a in adapters:
            g2 = sum(1 for f in a.channels if freq_to_band(f) == "2.4")
            g5 = sum(1 for f in a.channels if freq_to_band(f) == "5")
            dfs = sum(1 for f in a.channels if is_dfs(f))
            t.add_row(a.ifname, a.phy, a.driver, a.mac, str(g2), str(g5), str(dfs))
        console.print(t)
        plan = distribute({a.ifname: a.channels for a in adapters})
        console.print("\n[bold]Channel split with the adapters currently plugged in:[/]")
        for name, freqs in plan.items():
            console.print(f"  [cyan]{name}[/]  {len(freqs):>2} ch  {describe_channels(freqs)}", soft_wrap=True)
    ports = candidate_serial_ports(probe_other=True)
    console.print("\n[bold]Serial devices (possible GPS):[/]")
    if not ports:
        console.print("  none found (/dev/ttyACM*, /dev/ttyUSB*) - gpsd may still provide GPS")
    for port in ports:
        vid, pid, name = usb_ids(port)
        tag = "  [green]u-blox[/]" if vid == "1546" else ""
        console.print(f"  {port}  {vid}:{pid} {name}{tag}")
    return 0


def recover(cfg, console: Console) -> int:
    paths = recover_journals(cfg.output_path)
    if not paths:
        console.print("No unfinished session journals found.")
    for p in paths:
        console.print(f"[green]Recovered:[/] {p}")
    return 0


def choose_mode(args, cfg, console: Console) -> str:
    """CLI or GUI: explicit flag > config default > interactive chooser."""
    if args.gui:
        return "gui"
    if args.cli:
        return "cli"
    if cfg.ui.default_mode in ("cli", "gui"):
        return cfg.ui.default_mode
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    if not sys.stdin.isatty():  # e.g. started from a desktop launcher: the TUI cannot work
        return "gui" if has_display else "cli"
    console.print("[bold]Choose an interface:[/]")
    console.print("  [cyan]1[/]  CLI   terminal dashboard (works over SSH)")
    console.print("  [cyan]2[/]  GUI   desktop window (CustomTkinter)")
    default = "2" if has_display else "1"
    answer = Prompt.ask("Select", choices=["1", "2", "cli", "gui"], default=default, console=console)
    return "gui" if answer in ("2", "gui") else "cli"


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    console = Console()
    if args.version:
        print(f"Spejari {__version__}")
        return 0
    if not sys.platform.startswith("linux"):
        console.print("[red]Spejari runs on Linux only (Debian, Kali, Ubuntu, Raspberry Pi OS).[/]")
        return 1
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/]")
        return 2
    apply_overrides(cfg, args)

    if args.list_adapters:
        return list_adapters(cfg, console)
    if args.recover:
        return recover(cfg, console)

    print_banner(console)
    for warning in cfg.warnings:
        console.print(f"[yellow]config: {warning}[/]")
    if shutil.which("iw") is None:
        console.print("[red]'iw' is required. Install it with: sudo apt install iw[/]")
        return 1
    if os.geteuid() != 0:
        console.print("[red]Scanning needs root privileges. Run:  sudo ./run.sh   (or sudo python3 main.py)[/]")
        return 1

    mode = choose_mode(args, cfg, console)
    from .app import App  # imported late so --help/--list work without a TTY

    app = App(cfg, auto_start=args.auto_start)
    if mode == "gui":
        try:
            from .gui import run_gui
        except ImportError as exc:
            console.print(
                f"[red]The GUI needs CustomTkinter and Tk ({exc}).[/]\n"
                "Install with:  sudo apt install python3-tk   and   .venv/bin/pip install customtkinter\n"
                "(or run ./setup.sh), or use the terminal version with --cli."
            )
            return 1
        return run_gui(app)
    return app.run()
