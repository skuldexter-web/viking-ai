"""CustomTkinter desktop GUI for Spejari (same engine as the terminal dashboard)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

import customtkinter as ctk

from . import __version__
from .app import IDLE, RUNNING, STOPPING, App
from .channels import describe_channels, freq_to_channel
from .config import HARD_MAX_ADAPTERS
from .adapters import natural_key
from .gps import candidate_serial_ports, usb_ids
from .ui import fmt_duration

# Norse palette: night-sky background, steel-blue accents, gold highlights
BG = "#10131a"
CARD = "#1a1f2a"
CARD_2 = "#222938"
TEXT = "#d8dee9"
DIM = "#7d8798"
STEEL = "#6fa8dc"
GOLD = "#e0b84c"
GREEN = "#3fb768"
GREEN_HOVER = "#2f9a54"
RED = "#c8453b"
RED_HOVER = "#a8362e"
YELLOW = "#e5c07b"

BAND_CHOICES = ["Both: 2.4 + 5 GHz", "2.4 GHz only", "5 GHz only"]
SCAN_CHOICES = ["Active (probe requests)", "Passive (listen only)"]
GPS_SOURCES = ["auto", "gpsd", "serial", "none"]
FIX_CHOICES = ["2D or better", "3D fix only"]
AUTO_DEVICE = "auto-detect"
FEED_LIMIT = 1000


class SpejariGUI(ctk.CTk):
    def __init__(self, app: App) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        super().__init__()
        self.app = app
        self.cfg = app.cfg
        self.title(f"Spejari {__version__}  -  Wi-Fi war-driving scout")
        self.geometry("1320x880")
        self.minsize(1080, 700)
        self.configure(fg_color=BG)

        self._feed_total = 0
        self._adapter_sig: Optional[tuple] = None
        self._adapter_rows: Dict[str, Dict[str, ctk.CTkBaseClass]] = {}
        self._adapter_vars: Dict[str, tk.BooleanVar] = {}
        self._include_converted = False
        self._gps_apply_job: Optional[str] = None
        self._port_map: Dict[str, str] = {AUTO_DEVICE: ""}
        self._was_state = IDLE

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()
        self._build_statusbar()
        self._refresh_ports()
        self._load_options_into_widgets()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(250, self._tick)

    # ------------------------------------------------------------------ sidebar
    def _section(self, parent, text: str) -> None:
        ctk.CTkLabel(parent, text=text.upper(), text_color=STEEL, anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", padx=14, pady=(16, 4))

    def _menu(self, parent, label: str, values: List[str], command) -> ctk.CTkOptionMenu:
        ctk.CTkLabel(parent, text=label, text_color=DIM, anchor="w").pack(fill="x", padx=14, pady=(6, 0))
        menu = ctk.CTkOptionMenu(parent, values=values, command=command, fg_color=CARD_2,
                                 button_color="#2d3850", button_hover_color="#3a4866", dynamic_resizing=False)
        menu.pack(fill="x", padx=14, pady=(2, 0))
        return menu

    def _build_sidebar(self) -> None:
        side = ctk.CTkScrollableFrame(self, width=290, fg_color=CARD, corner_radius=0)
        side.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self._sidebar = side

        ctk.CTkLabel(side, text="ᛋ SPEJARI", text_color=GOLD,
                     font=ctk.CTkFont(size=28, weight="bold")).pack(padx=14, pady=(14, 0), anchor="w")
        ctk.CTkLabel(side, text=f"scout of the 2.4 / 5 GHz airwaves  ·  v{__version__}",
                     text_color=DIM, font=ctk.CTkFont(size=11)).pack(padx=14, anchor="w")

        self.btn_start = ctk.CTkButton(side, text="▶  Start session", height=46, fg_color=GREEN,
                                       hover_color=GREEN_HOVER, font=ctk.CTkFont(size=15, weight="bold"),
                                       command=self._toggle_session)
        self.btn_start.pack(fill="x", padx=14, pady=(18, 0))

        self._section(side, "Scan options")
        self.menu_band = self._menu(side, "Band", BAND_CHOICES, self._on_band)
        self.menu_scan = self._menu(side, "Scan type", SCAN_CHOICES, self._on_scan_type)
        self.menu_max = self._menu(side, f"Max adapters (1-{HARD_MAX_ADAPTERS})",
                                   [str(i) for i in range(1, HARD_MAX_ADAPTERS + 1)], self._on_max)
        self.switch_dfs_var = tk.BooleanVar(value=False)
        self.switch_dfs = ctk.CTkSwitch(side, text="Skip 5 GHz DFS channels", variable=self.switch_dfs_var,
                                        command=self._on_dfs, progress_color=STEEL)
        self.switch_dfs.pack(fill="x", padx=14, pady=(12, 0))

        self._section(side, "GPS")
        self.menu_gps = self._menu(side, "Source", GPS_SOURCES, self._on_gps_changed)
        self.menu_port = self._menu(side, "Serial device (u-blox)", [AUTO_DEVICE], self._on_gps_changed)
        self.btn_ports = ctk.CTkButton(side, text="↻  Rescan serial ports", height=28, fg_color=CARD_2,
                                       hover_color="#2d3850", command=self._refresh_ports)
        self.btn_ports.pack(fill="x", padx=14, pady=(6, 0))
        self.menu_fix = self._menu(side, "Required fix quality", FIX_CHOICES, self._on_fix)

        self._section(side, "Output (.csv)")
        self.lbl_outdir = ctk.CTkLabel(side, text="", text_color=TEXT, anchor="w", justify="left", wraplength=250)
        self.lbl_outdir.pack(fill="x", padx=14)
        row = ctk.CTkFrame(side, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(6, 0))
        row.grid_columnconfigure((0, 1), weight=1)
        self.btn_browse = ctk.CTkButton(row, text="Browse…", height=30, fg_color=CARD_2,
                                        hover_color="#2d3850", command=self._browse)
        self.btn_browse.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(row, text="Open folder", height=30, fg_color=CARD_2, hover_color="#2d3850",
                      command=self._open_folder).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        ctk.CTkButton(side, text="Quit", height=34, fg_color="transparent", border_width=1,
                      border_color=DIM, text_color=TEXT, hover_color=CARD_2,
                      command=self._on_close).pack(fill="x", padx=14, pady=(26, 14))

    # --------------------------------------------------------------------- main
    def _build_main(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=14, pady=(14, 6))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)

        # status cards
        cards = ctk.CTkFrame(main, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew")
        self._cards: Dict[str, ctk.CTkLabel] = {}
        spec = [("session", "SESSION"), ("ssids", "UNIQUE SSIDs"), ("bssids", "BSSIDs"),
                ("logged", "ROWS LOGGED"), ("km", "DISTANCE (km)"), ("gps", "GPS")]
        for i, (key, caption) in enumerate(spec):
            cards.grid_columnconfigure(i, weight=1, uniform="card")
            card = ctk.CTkFrame(cards, fg_color=CARD, corner_radius=10)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0 if i == len(spec) - 1 else 5))
            value = ctk.CTkLabel(card, text="-", text_color=GOLD if key in ("ssids", "km") else TEXT,
                                 font=ctk.CTkFont(size=22, weight="bold"))
            value.pack(padx=10, pady=(10, 0))
            ctk.CTkLabel(card, text=caption, text_color=DIM, font=ctk.CTkFont(size=10)).pack(pady=(0, 10))
            self._cards[key] = value

        self.lbl_gps = ctk.CTkLabel(main, text="", text_color=DIM, anchor="w", font=ctk.CTkFont(size=12))
        self.lbl_gps.grid(row=1, column=0, sticky="ew", pady=(8, 4))

        # adapters
        adapters_box = ctk.CTkFrame(main, fg_color="transparent")
        adapters_box.grid(row=2, column=0, sticky="ew")
        adapters_box.grid_columnconfigure(0, weight=1)
        self.lbl_adapters_title = ctk.CTkLabel(adapters_box, text="Adapters", text_color=STEEL, anchor="w",
                                               font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_adapters_title.grid(row=0, column=0, sticky="ew", pady=(4, 2))
        self.adapter_frame = ctk.CTkScrollableFrame(adapters_box, fg_color=CARD, height=268, corner_radius=10)
        self.adapter_frame.grid(row=1, column=0, sticky="ew")
        for col, weight in enumerate((0, 0, 0, 0, 1, 0, 0, 0)):
            self.adapter_frame.grid_columnconfigure(col, weight=weight)

        # live feed
        feed_box = ctk.CTkFrame(main, fg_color=CARD, corner_radius=10)
        feed_box.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        feed_box.grid_columnconfigure(0, weight=1)
        feed_box.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(feed_box, text="LIVE FEED", text_color=STEEL, anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Spejari.Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                        rowheight=22, borderwidth=0, bordercolor=CARD, lightcolor=CARD, darkcolor=CARD,
                        font="TkFixedFont")
        style.configure("Spejari.Treeview.Heading", background=CARD_2, foreground=STEEL, relief="flat",
                        font=("TkDefaultFont", 10, "bold"))
        style.map("Spejari.Treeview", background=[("selected", "#2b3a52")])
        style.map("Spejari.Treeview.Heading", background=[("active", CARD_2)])

        cols = ("time", "evt", "ssid", "bssid", "ch", "band", "rssi", "sec", "iface")
        self.tree = ttk.Treeview(feed_box, columns=cols, show="headings", style="Spejari.Treeview",
                                 selectmode="browse")
        widths = {"time": 76, "evt": 48, "ssid": 240, "bssid": 156, "ch": 40, "band": 50, "rssi": 55,
                  "sec": 90, "iface": 80}
        heads = {"time": "Time", "evt": "Evt", "ssid": "SSID", "bssid": "BSSID", "ch": "Ch", "band": "Band",
                 "rssi": "RSSI", "sec": "Security", "iface": "Iface"}
        for c in cols:
            self.tree.heading(c, text=heads[c], anchor="w")
            self.tree.column(c, width=widths[c], minwidth=40, stretch=(c == "ssid"), anchor="w")
        self.tree.tag_configure("NEW", foreground="#7ee787")
        self.tree.tag_configure("UPD", foreground="#9aa5b8")
        self.tree.tag_configure("OPEN", foreground="#ff8c82")
        self.tree.tag_configure("SYS", foreground="#79c0ff")
        self.tree.tag_configure("WARN", foreground=YELLOW)
        bar = ctk.CTkScrollbar(feed_box, command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        bar.grid(row=1, column=1, sticky="ns", padx=(0, 6), pady=(0, 8))

    def _build_statusbar(self) -> None:
        self.status = ctk.CTkLabel(self, text="Ready. Pick your options, then press Start session.",
                                   text_color=DIM, anchor="w", fg_color=CARD, corner_radius=0, height=28)
        self.status.grid(row=1, column=1, sticky="ew", padx=0, pady=0)

    # ----------------------------------------------------------- option handlers
    def _load_options_into_widgets(self) -> None:
        s, g = self.cfg.scan, self.cfg.gps
        if s.band_2g and s.band_5g:
            self.menu_band.set(BAND_CHOICES[0])
        else:
            self.menu_band.set(BAND_CHOICES[1] if s.band_2g else BAND_CHOICES[2])
        self.menu_scan.set(SCAN_CHOICES[1] if s.passive else SCAN_CHOICES[0])
        self.menu_max.set(str(s.max_adapters))
        self.switch_dfs_var.set(bool(s.skip_dfs))
        self.menu_gps.set(g.source)
        self.menu_fix.set(FIX_CHOICES[1] if g.min_fix_mode >= 3 else FIX_CHOICES[0])
        self._update_outdir_label()
        for label, port in self._port_map.items():
            if port and port == g.serial_port:
                self.menu_port.set(label)

    def _on_band(self, choice: str) -> None:
        self.cfg.scan.band_2g = choice != BAND_CHOICES[2]
        self.cfg.scan.band_5g = choice != BAND_CHOICES[1]

    def _on_scan_type(self, choice: str) -> None:
        self.cfg.scan.passive = choice == SCAN_CHOICES[1]

    def _on_max(self, choice: str) -> None:
        self.cfg.scan.max_adapters = int(choice)

    def _on_dfs(self) -> None:
        self.cfg.scan.skip_dfs = bool(self.switch_dfs_var.get())

    def _on_fix(self, choice: str) -> None:
        self.cfg.gps.min_fix_mode = 3 if choice == FIX_CHOICES[1] else 2

    def _on_gps_changed(self, _choice: str = "") -> None:
        self.cfg.gps.source = self.menu_gps.get()
        self.cfg.gps.serial_port = self._port_map.get(self.menu_port.get(), "")
        if self._gps_apply_job is not None:
            self.after_cancel(self._gps_apply_job)
        self._gps_apply_job = self.after(500, self._apply_gps)

    def _apply_gps(self) -> None:
        self._gps_apply_job = None
        if self.app.state == IDLE:
            self.app.restart_gps()
            self._set_status("GPS settings applied.", DIM)

    def _refresh_ports(self) -> None:
        self._port_map = {AUTO_DEVICE: ""}
        for port in candidate_serial_ports(probe_other=True):
            vid, _pid, name = usb_ids(port)
            tag = f" ({name})" if name else (" (u-blox)" if vid == "1546" else "")
            self._port_map[f"{port}{tag}"] = port
        current = self.menu_port.get() if hasattr(self, "menu_port") else AUTO_DEVICE
        self.menu_port.configure(values=list(self._port_map))
        self.menu_port.set(current if current in self._port_map else AUTO_DEVICE)

    def _update_outdir_label(self) -> None:
        self.lbl_outdir.configure(text=str(self.cfg.output_path))

    def _browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=str(self.cfg.output_path), title="Choose export folder")
        if chosen:
            self.cfg.log.output_dir = chosen
            self._update_outdir_label()

    def _open_folder(self) -> None:
        path = self.cfg.output_path
        path.mkdir(parents=True, exist_ok=True)
        cmd = ["xdg-open", str(path)]
        user = os.environ.get("SUDO_USER")
        if os.geteuid() == 0 and user:
            cmd = ["runuser", "-u", user, "--"] + cmd  # open it as the desktop user, not root
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            messagebox.showinfo("Export folder", str(path))

    # ------------------------------------------------------------------ session
    def _toggle_session(self) -> None:
        if self.app.state == IDLE:
            self.app.start_session()
        elif self.app.state == RUNNING:
            self.app.stop_session()

    def _on_close(self) -> None:
        if self.app.state == RUNNING:
            if not messagebox.askyesno("Spejari", "A session is running.\nStop it, export the CSV and quit?"):
                return
            self.app.stop_session(then_quit=True)
            self._set_status("Stopping and exporting before quit...", YELLOW)
            return
        if self.app.state == STOPPING:
            self.app.request_quit()
            return
        self.app.request_quit()

    def _set_status(self, text: str, color: str = DIM) -> None:
        self.status.configure(text="  " + text, text_color=color)

    # --------------------------------------------------------------------- tick
    @staticmethod
    def _cfg(widget, **kw) -> None:
        """configure() only when a value actually changed (avoids redraw flicker)."""
        last = getattr(widget, "_sp_kw", None)
        if last is None:
            last = widget._sp_kw = {}
        changed = {k: v for k, v in kw.items() if last.get(k) != v}
        if changed:
            last.update(changed)
            widget.configure(**changed)

    def _set(self, widget, text: str, color: Optional[str] = None) -> None:
        if color is None:
            self._cfg(widget, text=text)
        else:
            self._cfg(widget, text=text, text_color=color)

    def _tick(self) -> None:
        try:
            self._update()
        except tk.TclError:
            return  # window is being destroyed
        if self.app._quit_requested:
            if self.app.state == RUNNING:
                self.app.stop_session(then_quit=True)
            elif self.app.state == IDLE:
                self.destroy()
                return
        self.after(250, self._tick)

    def _update(self) -> None:
        app = self.app
        v = app.view()
        gps = v.gps

        # cards
        if v.state == RUNNING:
            self._set(self._cards["session"], f"● {fmt_duration(v.elapsed_s)}", GREEN)
        elif v.state == STOPPING:
            self._set(self._cards["session"], "exporting…", YELLOW)
        else:
            self._set(self._cards["session"], "○ idle", TEXT)
        self._set(self._cards["ssids"], str(v.unique_ssids))
        self._set(self._cards["bssids"], str(v.unique_bssids))
        self._set(self._cards["logged"], str(v.logged))
        self._set(self._cards["km"], f"{v.session_km:.3f}")
        gps_color = GREEN if gps.valid else (YELLOW if gps.connected else RED)
        self._set(self._cards["gps"], gps.status.split(" - ")[0], gps_color)

        # GPS detail line
        if gps.valid and gps.lat is not None and gps.lon is not None:
            alt = f"{gps.alt:.0f} m" if gps.alt is not None else "-"
            spd = f"{gps.speed_mps * 3.6:.0f} km/h" if gps.speed_mps is not None else "-"
            hdop = f"  ·  HDOP {gps.hdop:.1f}" if gps.hdop is not None else ""
            detail = (f"{gps.lat:+.6f}, {gps.lon:+.6f}   ·   alt {alt}   ·   {spd}   ·   "
                      f"sats {gps.sats_used}/{gps.sats_seen}{hdop}   ·   {gps.device or gps.source}")
        else:
            detail = f"GPS: {gps.status}"
        self._set(self.lbl_gps, detail)

        # buttons / locked controls
        if v.state == IDLE:
            self._cfg(self.btn_start, text="▶  Start session", state="normal", fg_color=GREEN,
                      hover_color=GREEN_HOVER)
        elif v.state == RUNNING:
            self._cfg(self.btn_start, text="■  Stop & export CSV", state="normal", fg_color=RED,
                      hover_color=RED_HOVER)
        else:
            self._cfg(self.btn_start, text="Exporting…", state="disabled")
        lock = "normal" if v.state == IDLE else "disabled"
        for w in (self.menu_gps, self.menu_port, self.btn_ports, self.btn_browse):
            self._cfg(w, state=lock)

        # state transitions -> status bar
        if self._was_state != IDLE and v.state == IDLE and app.last_export:
            self._set_status(f"Exported: {app.last_export_path or app.last_export}", GREEN)
        elif self._was_state == IDLE and v.state == RUNNING:
            self._set_status("Session running - scanning and logging.", GREEN)
        self._was_state = v.state

        # one-shot auto start
        if app.auto_start and v.state == IDLE and v.adapters:
            app.auto_start = False
            app.start_session()

        self._update_adapters(v)
        self._update_feed()

    # ----------------------------------------------------------------- adapters
    def _update_adapters(self, v) -> None:
        active = {a.ifname: a for a in v.adapters}
        skipped = {s["ifname"]: s for s in self.app.engine.skipped_adapters()}
        scan = self.cfg.scan

        if not self._include_converted and scan.include_interfaces and (active or skipped):
            names = set(active) | set(skipped)
            scan.exclude_interfaces = sorted(set(scan.exclude_interfaces) | (names - set(scan.include_interfaces)))
            scan.include_interfaces = []
            self._include_converted = True

        names = sorted(set(active) | set(skipped), key=natural_key)
        total = len({f for a in v.adapters for f in a.channels})
        self._set(self.lbl_adapters_title,
                  f"ADAPTERS  {len(active)} active of {scan.max_adapters}   ·   {total} channels shared   ·   "
                  "tick \"Use\" to include an adapter (hot-plug is automatic)")

        sig = tuple(names)
        if sig != self._adapter_sig:
            self._rebuild_adapter_rows(names, active, skipped)
            self._adapter_sig = sig
        if not names:
            return
        for name in names:
            row = self._adapter_rows.get(name)
            if not row:
                continue
            a = active.get(name)
            if a is not None:
                now = ",".join(str(freq_to_channel(f)) for f in a.current) or "-"
                assigned = describe_channels(a.channels)
                if len(assigned) > 70:
                    assigned = assigned[:69] + "…"
                state_color = GREEN if a.state == "scanning" else (DIM if a.state == "idle" else YELLOW)
                self._set(row["ch"], str(len(a.channels)))
                self._set(row["assigned"], assigned)
                self._set(row["now"], now)
                self._set(row["hits"], str(a.hits))
                self._set(row["state"], a.state, state_color)
                self._set(row["driver"], a.driver)
            else:
                s = skipped.get(name, {})
                self._set(row["ch"], "-")
                self._set(row["assigned"], "-")
                self._set(row["now"], "-")
                self._set(row["hits"], "-")
                self._set(row["state"], s.get("reason", "unused"), DIM)
                self._set(row["driver"], s.get("driver", "?"))

    def _rebuild_adapter_rows(self, names: List[str], active, skipped) -> None:
        for child in self.adapter_frame.winfo_children():
            child.destroy()
        self._adapter_rows.clear()
        self._adapter_vars.clear()
        headers = ["Use", "Iface", "Driver", "Ch", "Assigned channels", "Now", "Hits", "State"]
        for col, h in enumerate(headers):
            ctk.CTkLabel(self.adapter_frame, text=h, text_color=STEEL, anchor="w",
                         font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=col, sticky="w", padx=8)
        if not names:
            ctk.CTkLabel(self.adapter_frame, text="No scan-capable wireless adapter detected - plug one in, "
                         "Spejari hot-plugs.", text_color=YELLOW).grid(row=1, column=0, columnspan=8,
                                                                        sticky="w", padx=8, pady=10)
            return
        for r, name in enumerate(names, start=1):
            var = tk.BooleanVar(value=name not in self.cfg.scan.exclude_interfaces)
            self._adapter_vars[name] = var
            ctk.CTkCheckBox(self.adapter_frame, text="", variable=var, width=24, checkbox_width=18,
                            checkbox_height=18, command=lambda n=name: self._on_adapter_toggle(n)
                            ).grid(row=r, column=0, padx=(8, 0), pady=2)
            widgets: Dict[str, ctk.CTkBaseClass] = {}
            ctk.CTkLabel(self.adapter_frame, text=name, text_color=GOLD, anchor="w",
                         font=ctk.CTkFont(weight="bold")).grid(row=r, column=1, sticky="w", padx=8)
            for col, key in enumerate(("driver", "ch", "assigned", "now", "hits", "state"), start=2):
                lbl = ctk.CTkLabel(self.adapter_frame, text="", anchor="w", text_color=TEXT)
                lbl.grid(row=r, column=col, sticky="w", padx=8)
                widgets[key] = lbl
            self._adapter_rows[name] = widgets

    def _on_adapter_toggle(self, name: str) -> None:
        excl = set(self.cfg.scan.exclude_interfaces)
        if self._adapter_vars[name].get():
            excl.discard(name)
        else:
            excl.add(name)
        self.cfg.scan.exclude_interfaces = sorted(excl)

    # --------------------------------------------------------------------- feed
    def _update_feed(self) -> None:
        entries, self._feed_total = self.app.feed.since(self._feed_total)
        if not entries:
            return
        at_bottom = self.tree.yview()[1] >= 0.97
        for e in entries[-300:]:
            ts = datetime.fromtimestamp(e.ts).strftime("%H:%M:%S")
            if e.kind in ("SYS", "WARN"):
                self.tree.insert("", "end", values=(ts, e.kind, _clean(e.message), "", "", "", "", "", ""),
                                 tags=(e.kind,))
                continue
            tag = "OPEN" if e.security in ("Open", "WEP") else e.kind
            ssid = "<hidden>" if e.ssid == "" else _clean(e.ssid)
            self.tree.insert("", "end", values=(ts, e.kind, ssid, e.bssid, e.channel, f"{e.band}G", e.rssi,
                                                e.security, e.adapter), tags=(tag,))
        children = self.tree.get_children()
        if len(children) > FEED_LIMIT:
            self.tree.delete(*children[: len(children) - FEED_LIMIT])
        if at_bottom:
            self.tree.yview_moveto(1.0)


def _clean(text: str) -> str:
    """Replace control characters (SSIDs are attacker-controlled)."""
    return "".join(ch if ch.isprintable() else "·" for ch in text)


def run_gui(app: App) -> int:
    signal.signal(signal.SIGTERM, app.request_quit)
    signal.signal(signal.SIGINT, app.request_quit)
    try:
        gui = SpejariGUI(app)
    except tk.TclError as exc:
        print(f"Cannot open a display: {exc}", file=sys.stderr)
        print("Run from a desktop session. With sudo, keep DISPLAY/XAUTHORITY (./run.sh --gui does this) or run:\n"
              "  xhost +SI:localuser:root", file=sys.stderr)
        return 1
    app.startup()
    try:
        gui.mainloop()
    finally:
        app.shutdown()
    for path in app.exported_paths:
        print(f"Exported: {path}")
    return 0
