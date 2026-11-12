"""Application controller: wires GPS, scan engine, session, exporter and UI together."""

from __future__ import annotations

import signal
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.live import Live

from .config import Config
from .exporter import Journal, export_filename, normalize_csv_path, write_wigle_csv
from .gps import GpsMonitor
from .models import FeedLog
from .scanner import ScanEngine
from .session import Session
from .ui import DashboardView, KeyReader, render_dashboard

IDLE, RUNNING, STOPPING = "IDLE", "RUNNING", "STOPPING"


class App:
    def __init__(self, cfg: Config, auto_start: bool = False) -> None:
        self.cfg = cfg
        self.auto_start = auto_start
        self.console = Console()
        self.feed = FeedLog(cfg.ui.feed_history)
        self.gps = GpsMonitor(cfg.gps)
        self.engine = ScanEngine(cfg, self.gps, self.feed)
        self.state = IDLE
        self.session: Optional[Session] = None
        self.journal: Optional[Journal] = None
        self.last_export = ""
        self.last_export_path: Optional[Path] = None
        self.last_stats = None  # SessionStats of the finished session (kept on screen)
        self.last_km = 0.0
        self.exported_paths = []
        self._started = False
        self._quit_requested = False
        self._lock = threading.Lock()

    # -- session control ---------------------------------------------------------
    def start_session(self) -> None:
        with self._lock:
            if self.state != IDLE:
                return
            if self.engine.adapter_count() == 0:
                self.feed.system("Cannot start: no wireless adapter detected", warn=True)
                return
            started = datetime.now()
            self.journal = Journal(self.cfg.output_path, started)
            session = Session(self.cfg, self.feed, self.journal)
            session.started_local = started
            session.distance_baseline_m = self.gps.snapshot().distance_m
            self.session = session
            self.last_stats = None
            self.last_km = 0.0
            self.state = RUNNING
        self.engine.begin_session(session)
        self.feed.system("Session started - scanning and logging")
        if not self.gps.snapshot().valid:
            self.feed.system("Waiting for GPS fix: networks are shown but only logged once there is a fix", warn=True)

    def stop_session(self, then_quit: bool = False) -> None:
        with self._lock:
            if self.state != RUNNING:
                return
            self.state = STOPPING
        threading.Thread(target=self._finish, args=(then_quit,), name="spejari-export", daemon=True).start()

    def _finish(self, then_quit: bool) -> None:
        try:
            session = self.engine.end_session()
            km = max(0.0, self.gps.snapshot().distance_m - (session.distance_baseline_m if session else 0.0)) / 1000.0
            if session is not None:
                self.last_stats, self.last_km = session.stats(), km
            if session is None or not session.observations:
                self.last_export = "nothing exported (no networks with GPS fix)"
                self.feed.system("Session stopped: no observations with a GPS fix, no CSV written", warn=True)
                if self.journal:
                    self.journal.discard()
            else:
                path = normalize_csv_path(self.cfg.output_path / export_filename(session.started_local))
                rows = write_wigle_csv(session.observations, path)
                st = session.stats()
                self.last_export = f"{path.name} ({rows} rows)"
                self.exported_paths.append(path)
                self.last_export_path = path
                self.feed.system(
                    f"Exported {rows} rows / {st.unique_bssids} networks / {km:.2f} km -> {path}"
                )
                if self.journal:
                    self.journal.discard()
        except Exception as exc:  # the journal on disk still holds the data
            self.feed.system(f"Export failed: {exc} (use --recover to rebuild from journal)", warn=True)
        finally:
            self.journal = None
            self.session = None
            self.state = IDLE
            if then_quit:
                self._quit_requested = True

    def request_quit(self, *_args) -> None:
        self._quit_requested = True

    # -- lifecycle shared by the terminal dashboard and the GUI --------------------
    def startup(self) -> None:
        if self._started:
            return
        self._started = True
        self.gps.start()
        self.engine.start()

    def shutdown(self) -> None:
        self.engine.shutdown()
        self.gps.stop()
        if self.journal:  # only reachable on an unexpected exit
            self.journal.close()

    def restart_gps(self) -> None:
        """Apply new GPS settings (source / device). Only call while idle."""
        old = self.gps
        old.stop()

        def swap() -> None:
            if old.is_alive():
                old.join(timeout=5.0)
            new = GpsMonitor(self.cfg.gps)
            self.gps = new
            self.engine.gps = new
            new.start()

        threading.Thread(target=swap, name="spejari-gps-restart", daemon=True).start()

    # -- view --------------------------------------------------------------------
    def view(self) -> DashboardView:
        gps = self.gps.snapshot()
        session = self.session
        v = DashboardView(
            state=self.state,
            gps=gps,
            adapters=self.engine.adapter_views(),
            max_adapters=self.cfg.scan.max_adapters,
            feed=self.feed.tail(200),
            last_export=self.last_export,
            utc_now=self.gps.utc_now(),
        )
        if session is not None:
            st = session.stats()
            v.elapsed_s = session.elapsed
            v.unique_ssids, v.unique_bssids, v.hidden = st.unique_ssids, st.unique_bssids, st.hidden
            v.logged, v.seen_no_fix = st.logged, st.seen_no_fix
            v.session_km = max(0.0, gps.distance_m - session.distance_baseline_m) / 1000.0
        elif self.last_stats is not None:  # show the finished session's totals until the next start
            st = self.last_stats
            v.unique_ssids, v.unique_bssids, v.hidden = st.unique_ssids, st.unique_bssids, st.hidden
            v.logged, v.seen_no_fix, v.session_km = st.logged, st.seen_no_fix, self.last_km
        return v

    # -- main loop ---------------------------------------------------------------
    def _on_key(self, key: str) -> None:
        if key == "s":
            if self.state == IDLE:
                self.start_session()
            elif self.state == RUNNING:
                self.stop_session()
        elif key == "q":
            self.request_quit()

    def run(self) -> int:
        signal.signal(signal.SIGINT, self.request_quit)
        signal.signal(signal.SIGTERM, self.request_quit)
        self.startup()
        if self.auto_start or not KeyReader().enabled:
            deadline = time.monotonic() + 8
            while self.engine.adapter_count() == 0 and time.monotonic() < deadline:
                time.sleep(0.2)
            self.start_session()
        interval = 1.0 / self.cfg.ui.refresh_hz
        try:
            with KeyReader() as keys, Live(
                render_dashboard(self.view()), console=self.console, screen=True, auto_refresh=False
            ) as live:
                while True:
                    for key in keys.read(interval):
                        self._on_key(key)
                    if self._quit_requested:
                        if self.state == RUNNING:
                            self.stop_session(then_quit=True)
                        elif self.state == IDLE:
                            break
                    live.update(render_dashboard(self.view()), refresh=True)
        finally:
            self.shutdown()
        for path in self.exported_paths:
            self.console.print(f"[bold green]Exported:[/] {path}")
        return 0
