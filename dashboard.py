#!/usr/bin/env python3
"""
Server Dashboard
=================
A fullscreen tkinter dashboard for monitoring a Linux server: CPU, memory,
disk, network, temperature, load average, and top processes. Includes an
idle screensaver, threshold-based color coding, and an Apps panel for
launching linked applications (e.g. Splunk).

Run: python3 dashboard.py
Quit: Escape key
Toggle fullscreen: F11
Toggle Apps panel: click "APPS" in the header
"""

import collections
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime

import tkinter as tk

try:
    import psutil
except ImportError:
    print("ERROR: psutil is required. Install it with: pip install psutil")
    sys.exit(1)

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ============================================================
# CONFIG  (edit these to taste)
# ============================================================

class Config:
    # --- Behavior ---
    FULLSCREEN_ON_START = True
    IDLE_SECONDS = 60          # seconds of inactivity before screensaver
    REFRESH_MS = 1000          # dashboard refresh interval
    HISTORY_LENGTH = 60        # data points kept for sparkline graphs

    # --- Screensaver ---
    SCREENSAVER_IMAGE = "/root/dashboard/images.jpg"

    # --- Monitoring ---
    DISK_PATH = "/"
    NET_INTERFACE = None       # None = sum of all interfaces
    TOP_PROCESS_COUNT = 5

    # --- Thresholds (percent) for color coding ---
    THRESHOLD_WARN = 60
    THRESHOLD_CRIT = 85

    # --- Apps panel ---
    # Each entry needs a "name" plus either a "url" (opened via BROWSER_CANDIDATES,
    # see below) or a "command" (a list, passed straight to subprocess.Popen,
    # e.g. ["xterm"] or ["/usr/bin/some-tool", "--flag"]). If you know exactly
    # which browser is installed on this machine, it's more reliable to skip
    # "url" entirely and specify "command" directly, e.g.:
    #   {"name": "Splunk", "command": ["chromium-browser", "--new-window", "https://splunk.example.com"]}
    APPS = [
        {"name": "Splunk", "url": "https://splunk.example.com"},
        # {"name": "Grafana", "url": "https://grafana.example.com"},
        # {"name": "Terminal", "command": ["xterm"]},
    ]

    # --- Browser launch (used only for APPS entries with "url") ---
    # Tried in order; the first binary found on PATH (via shutil.which) is
    # used. We do NOT rely on the webbrowser module / update-alternatives
    # "www-browser" symlink, because on minimal/kiosk Linux installs that
    # symlink is frequently unset and fails with a raw, uncatchable
    # "failed to execute child process www-browser" error printed straight
    # to stderr instead of a normal Python exception.
    BROWSER_CANDIDATES = [
        ["xdg-open", "{url}"],
        ["google-chrome", "--new-window", "{url}"],
        ["chromium-browser", "--new-window", "{url}"],
        ["chromium", "--new-window", "{url}"],
        ["firefox", "--new-window", "{url}"],
    ]

    # --- Logging ---
    LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.log")


# ============================================================
# COLORS / THEME
# ============================================================

BG = "#050505"
PANEL = "#0d0d0d"
PANEL_ALT = "#111111"

RED = "#ff2020"
DARK_RED = "#8b0000"
RED_DIM = "#b30000"

GREEN = "#8b0000"
YELLOW = "#f1c40f"

TEXT = "#ffffff"
DIM = "#777777"
DIM2 = "#4d4d4d"


def status_color(percent):
    """Return a color based on how hot a metric is."""
    if percent is None:
        return DIM
    if percent >= Config.THRESHOLD_CRIT:
        return RED
    if percent >= Config.THRESHOLD_WARN:
        return YELLOW
    return GREEN


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    filename=Config.LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def safe(fn, default=None, label=""):
    """Run fn() and log+swallow any exception, returning default instead."""
    try:
        return fn()
    except Exception as error:
        logging.warning("safe() failed for %s: %s", label or fn, error)
        return default


# ============================================================
# HELPERS
# ============================================================

def get_local_ip():
    """
    Get the machine's real LAN IP. socket.gethostbyname(hostname) is
    unreliable on servers (often returns 127.0.1.1 or raises), so we open
    a UDP "connection" instead -- no packets are actually sent.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "Unavailable"
    finally:
        s.close()


def format_bytes_per_sec(bytes_per_sec):
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if bytes_per_sec < 1024:
            return f"{bytes_per_sec:.1f} {unit}"
        bytes_per_sec /= 1024
    return f"{bytes_per_sec:.1f} TB/s"


def format_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ============================================================
# SPARKLINE (rolling history graph on a Canvas)
# ============================================================

class Sparkline(tk.Canvas):
    def __init__(self, parent, color=RED, height=36, width=60, maxlen=Config.HISTORY_LENGTH, **kwargs):
        # Small explicit width so this widget doesn't force its parent to
        # request Tk's oversized default Canvas width (200px). Packed with
        # fill="x" it will still stretch to whatever space is available.
        super().__init__(
            parent, bg=PANEL, height=height, width=width, highlightthickness=0, **kwargs
        )
        self.color = color
        self.data = collections.deque([0] * maxlen, maxlen=maxlen)
        self.bind("<Configure>", lambda e: self.redraw())

    def push(self, value):
        self.data.append(max(0, min(100, value)))
        self.redraw()

    def redraw(self):
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            return

        n = len(self.data)
        if n < 2:
            return

        step = width / (n - 1)
        points = []
        for i, value in enumerate(self.data):
            x = i * step
            y = height - (value / 100) * height
            points.extend([x, y])

        # baseline
        self.create_line(0, height - 1, width, height - 1, fill="#1a1a1a")

        self.create_line(*points, fill=self.color, width=2, smooth=True)


# ============================================================
# MAIN APP
# ============================================================

class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Server Dashboard")
        self.configure(bg=BG)

        self.is_fullscreen = Config.FULLSCREEN_ON_START
        self.attributes("-fullscreen", self.is_fullscreen)

        # Screensaver state
        self.screensaver_active = False
        self.last_activity = time.time()
        self.screensaver_image = None

        # View state ("dashboard" or "apps")
        self.current_view = "dashboard"

        # Cache which browser binary works, so we only probe PATH once.
        self._resolved_browser_cmd = None
        self._browser_probe_done = False

        # Network / disk I/O baselines (for rate calculation)
        self._last_net = safe(psutil.net_io_counters, label="net_io_counters")
        self._last_disk_io = safe(psutil.disk_io_counters, label="disk_io_counters")
        self._last_sample_time = time.time()

        # Prime CPU percent (first call always returns 0.0)
        safe(lambda: psutil.cpu_percent(percpu=True), label="cpu_percent priming")

        # ----------------------------------------------------
        # Global key bindings
        # ----------------------------------------------------
        self.bind_all("<Motion>", self.user_activity)
        self.bind_all("<Key>", self.user_activity)
        self.bind_all("<Button>", self.user_activity)
        self.bind("<Escape>", lambda e: self.quit_app())
        self.bind("<F11>", lambda e: self.toggle_fullscreen())

        self.create_ui()
        self.update_dashboard()
        self.check_idle()

    def quit_app(self):
        self.destroy()

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    # ========================================================
    # UI CONSTRUCTION
    # ========================================================

    def create_ui(self):
        self.create_header()
        self.create_separator()

        # Body area holds both the dashboard view and the apps view,
        # stacked in the same grid cell so we can flip between them
        # with tkraise() instead of destroying/rebuilding widgets.
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)

        self.dashboard_frame = tk.Frame(self.body, bg=BG)
        self.apps_frame = tk.Frame(self.body, bg=BG)
        self.dashboard_frame.grid(row=0, column=0, sticky="nsew")
        self.apps_frame.grid(row=0, column=0, sticky="nsew")

        self.create_info_row(self.dashboard_frame)
        self.create_resource_row(self.dashboard_frame)
        self.create_secondary_row(self.dashboard_frame)
        self.create_process_row(self.dashboard_frame)
        self.create_footer(self.dashboard_frame)

        self.create_apps_view(self.apps_frame)

        self.show_dashboard_view()

    def create_header(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=18, pady=(8, 4))

        # Top row: title (left) + APPS button (right). Only two widgets share
        # this row, so the button can never get squeezed off-screen by a
        # long date/clock string on narrow displays.
        top_row = tk.Frame(header, bg=BG)
        top_row.pack(fill="x")

        tk.Label(
            top_row, text="SERVER DASHBOARD", bg=BG, fg=RED,
            font=("Segoe UI", 18, "bold")
        ).pack(side="left")

        self.nav_button = tk.Button(
            top_row, text="APPS \u25b8", command=self.toggle_view,
            bg=PANEL, fg=RED, activebackground=DARK_RED, activeforeground=TEXT,
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
            padx=14, pady=5, cursor="hand2",
            highlightbackground=DARK_RED, highlightthickness=1,
        )
        self.nav_button.pack(side="right")

        # Bottom row: date + clock, smaller and out of the button's way.
        bottom_row = tk.Frame(header, bg=BG)
        bottom_row.pack(fill="x", pady=(2, 0))

        self.clock = tk.Label(
            bottom_row, text="00:00:00", bg=BG, fg=TEXT, font=("Segoe UI", 13, "bold")
        )
        self.clock.pack(side="right")

        self.date = tk.Label(bottom_row, text="", bg=BG, fg=DIM, font=("Segoe UI", 9))
        self.date.pack(side="right", padx=(0, 12))

    def create_separator(self):
        tk.Frame(self, bg=RED, height=2).pack(fill="x", padx=18)

    def create_info_row(self, parent):
        info = tk.Frame(parent, bg=BG)
        info.pack(fill="x", padx=18, pady=4)

        self.hostname = self.create_info_card(info, "HOSTNAME")
        self.ip = self.create_info_card(info, "IP ADDRESS")
        self.uptime = self.create_info_card(info, "UPTIME")
        self.loadavg = self.create_info_card(info, "LOAD AVG (1/5/15m)")

    def create_info_card(self, parent, title):
        frame = tk.Frame(parent, bg=PANEL, highlightbackground=DARK_RED, highlightthickness=1)
        frame.pack(side="left", fill="both", expand=True, padx=6)

        tk.Label(
            frame, text=title, bg=PANEL, fg=RED_DIM, font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=12, pady=(6, 1))

        value = tk.Label(
            frame, text="Loading...", bg=PANEL, fg=TEXT, font=("Segoe UI", 13, "bold")
        )
        value.pack(anchor="w", padx=12, pady=(0, 6))
        return value

    def create_resource_row(self, parent):
        resources = tk.Frame(parent, bg=BG)
        resources.pack(fill="both", expand=True, padx=18, pady=3)

        self.cpu = self.create_resource_panel(resources, "CPU USAGE")
        self.ram = self.create_resource_panel(resources, "MEMORY")
        self.disk = self.create_resource_panel(resources, "DISK")

    def create_resource_panel(self, parent, title):
        frame = tk.Frame(parent, bg=PANEL, highlightbackground=DARK_RED, highlightthickness=1)
        frame.pack(side="left", fill="both", expand=True, padx=8)

        tk.Label(
            frame, text=title, bg=PANEL, fg=RED_DIM, font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=14, pady=(6, 1))

        value = tk.Label(frame, text="0%", bg=PANEL, fg=TEXT, font=("Segoe UI", 22, "bold"))
        value.pack(pady=(1, 1))

        detail = tk.Label(frame, text="", bg=PANEL, fg=DIM, font=("Segoe UI", 9))
        detail.pack(pady=(0, 3))

        bar_bg = tk.Frame(frame, bg="#222222", height=5)
        bar_bg.pack(fill="x", padx=14)
        bar = tk.Frame(bar_bg, bg=GREEN, height=5)
        bar.place(x=0, y=0, relheight=1, relwidth=0)

        spark = Sparkline(frame, color=RED, height=18)
        spark.pack(fill="x", padx=14, pady=(4, 2))

        # per-core mini bars only meaningful for CPU; created lazily below
        cores_frame = tk.Frame(frame, bg=PANEL)
        cores_frame.pack(fill="x", padx=14, pady=(0, 5))

        return {
            "value": value,
            "detail": detail,
            "bar": bar,
            "spark": spark,
            "cores_frame": cores_frame,
            "core_bars": [],
        }

    def create_secondary_row(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=18, pady=3)

        self.network = self.create_secondary_card(row, "NETWORK I/O")
        self.swap = self.create_secondary_card(row, "SWAP")
        self.temp = self.create_secondary_card(row, "TEMPERATURE")

    def create_secondary_card(self, parent, title):
        frame = tk.Frame(parent, bg=PANEL, highlightbackground=DARK_RED, highlightthickness=1)
        frame.pack(side="left", fill="both", expand=True, padx=6)

        tk.Label(
            frame, text=title, bg=PANEL, fg=RED_DIM, font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", padx=12, pady=(6, 1))

        value = tk.Label(
            frame, text="\u2014", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold"), justify="left"
        )
        value.pack(anchor="w", padx=12, pady=(0, 6))
        return value

    def create_process_row(self, parent):
        frame = tk.Frame(parent, bg=PANEL, highlightbackground=DARK_RED, highlightthickness=1)
        frame.pack(fill="x", padx=18, pady=3)

        tk.Label(
            frame, text="TOP PROCESSES (CPU)", bg=PANEL, fg=RED_DIM,
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", padx=12, pady=(6, 2))

        self.process_labels = []
        rows = tk.Frame(frame, bg=PANEL)
        rows.pack(fill="x", padx=12, pady=(0, 6))

        for _ in range(Config.TOP_PROCESS_COUNT):
            row = tk.Frame(rows, bg=PANEL)
            row.pack(fill="x", pady=1)

            name = tk.Label(row, text="\u2014", bg=PANEL, fg=TEXT, font=("Consolas", 10), width=24, anchor="w")
            name.pack(side="left")

            cpu = tk.Label(row, text="", bg=PANEL, fg=DIM, font=("Consolas", 10), width=9, anchor="e")
            cpu.pack(side="left")

            mem = tk.Label(row, text="", bg=PANEL, fg=DIM, font=("Consolas", 10), width=9, anchor="e")
            mem.pack(side="left")

            self.process_labels.append({"name": name, "cpu": cpu, "mem": mem})

    def create_footer(self, parent):
        footer = tk.Frame(parent, bg=BG)
        footer.pack(fill="x", padx=18, pady=4)

        self.status = tk.Label(
            footer, text="\u25cf SYSTEM ONLINE", bg=BG, fg=GREEN, font=("Segoe UI", 12, "bold")
        )
        self.status.pack(side="left")

        tk.Label(
            footer,
            text=f"AFK SCREENSAVER: {Config.IDLE_SECONDS}s   |   ESC quit   |   F11 toggle fullscreen",
            bg=BG, fg=DIM, font=("Segoe UI", 9)
        ).pack(side="right")

    # ========================================================
    # APPS VIEW
    # ========================================================

    def create_apps_view(self, parent):
        tk.Label(
            parent, text="APPS", bg=BG, fg=RED, font=("Segoe UI", 18, "bold")
        ).pack(anchor="w", padx=18, pady=(16, 2))

        tk.Label(
            parent, text="Launch a linked application", bg=BG, fg=DIM,
            font=("Segoe UI", 10)
        ).pack(anchor="w", padx=18, pady=(0, 12))

        grid_frame = tk.Frame(parent, bg=BG)
        grid_frame.pack(fill="both", expand=True, padx=18, pady=6)

        columns = 3
        for i in range(columns):
            grid_frame.grid_columnconfigure(i, weight=1, uniform="apps")

        if not Config.APPS:
            tk.Label(
                grid_frame, text="No apps configured. Add entries to Config.APPS.",
                bg=BG, fg=DIM, font=("Segoe UI", 11)
            ).grid(row=0, column=0, columnspan=columns, pady=30)
        else:
            for index, app in enumerate(Config.APPS):
                row, col = divmod(index, columns)
                self.create_app_tile(grid_frame, app, row, col)

        footer = tk.Frame(parent, bg=BG)
        footer.pack(fill="x", padx=18, pady=(6, 12), side="bottom")
        tk.Label(
            footer,
            text="ESC quit   |   F11 fullscreen   |   Click APPS to return",
            bg=BG, fg=DIM, font=("Segoe UI", 8)
        ).pack(side="right")

    def create_app_tile(self, parent, app, row, col):
        tile = tk.Frame(parent, bg=PANEL, highlightbackground=DARK_RED, highlightthickness=1)
        tile.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        name_label = tk.Label(
            tile, text=app.get("name", "App"), bg=PANEL, fg=TEXT,
            font=("Segoe UI", 14, "bold")
        )
        name_label.pack(padx=20, pady=(24, 6))

        subtitle = app.get("url") or " ".join(app.get("command", [])) or "No target configured"
        subtitle_label = tk.Label(
            tile, text=subtitle, bg=PANEL, fg=DIM, font=("Segoe UI", 9), wraplength=180
        )
        subtitle_label.pack(padx=20, pady=(0, 16))

        launch_btn = tk.Button(
            tile, text="LAUNCH", command=lambda a=app: self.launch_app(a),
            bg=BG, fg=RED, activebackground=DARK_RED, activeforeground=TEXT,
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
            padx=14, pady=6, cursor="hand2",
        )
        launch_btn.pack(pady=(0, 20))

        # Let clicking anywhere on the tile (not just the button) launch it.
        for widget in (tile, name_label, subtitle_label):
            widget.bind("<Button-1>", lambda e, a=app: self.launch_app(a))
            widget.config(cursor="hand2")

    def launch_app(self, app):
        name = app.get("name", "app")
        try:
            if app.get("url"):
                self._open_url(app["url"], name)
            elif app.get("command"):
                subprocess.Popen(app["command"])
                logging.info("Launched app '%s' via command: %s", name, app["command"])
            else:
                logging.warning("App '%s' has no url or command configured", name)
        except Exception as error:
            logging.error("Failed to launch app '%s': %s", name, error)

    def _resolve_browser_cmd(self):
        """
        Find the first working browser command from Config.BROWSER_CANDIDATES,
        based on what's actually on PATH. Cached after the first successful
        probe so repeated launches don't re-scan the filesystem.

        We deliberately do NOT use Python's webbrowser module here. On
        minimal/kiosk Linux installs, webbrowser.open() falls back to the
        update-alternatives "www-browser" symlink, which is frequently
        unset and fails with a raw
            "failed to execute child process 'www-browser'"
        error printed straight to stderr -- not a catchable Python
        exception -- so a try/except around webbrowser.open() doesn't
        actually protect you from it.
        """
        if self._resolved_browser_cmd is not None:
            return self._resolved_browser_cmd

        self._browser_probe_done = True
        for template in Config.BROWSER_CANDIDATES:
            binary = template[0]
            if shutil.which(binary):
                self._resolved_browser_cmd = template
                logging.info("Resolved browser for URL launches: %s", binary)
                return template

        logging.error(
            "No working browser found on PATH. Tried: %s. "
            "Install one of these, or set Config.APPS entries to use "
            "\"command\" instead of \"url\" with the exact binary path.",
            ", ".join(t[0] for t in Config.BROWSER_CANDIDATES),
        )
        return None

    def _open_url(self, url, name):
        template = self._resolve_browser_cmd()
        if template is None:
            logging.error("Cannot launch app '%s': no browser available", name)
            return

        cmd = [part.format(url=url) for part in template]
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logging.info("Launched app '%s' via %s: %s", name, cmd[0], url)
        except Exception as error:
            # This binary was on PATH but failed to actually run (e.g. a
            # broken symlink). Drop the cached choice so the next launch
            # re-probes instead of retrying the same broken command forever.
            logging.error("Browser '%s' failed for app '%s': %s", cmd[0], name, error)
            self._resolved_browser_cmd = None

    def toggle_view(self):
        if self.current_view == "dashboard":
            self.show_apps_view()
        else:
            self.show_dashboard_view()

    def show_dashboard_view(self):
        self.current_view = "dashboard"
        self.dashboard_frame.tkraise()
        self.nav_button.config(text="APPS \u25b8")

    def show_apps_view(self):
        self.current_view = "apps"
        self.apps_frame.tkraise()
        self.nav_button.config(text="\u25c2 DASHBOARD")

    # ========================================================
    # DASHBOARD UPDATE
    # ========================================================

    def update_dashboard(self):
        try:
            self._update_dashboard_impl()
        except Exception as error:
            logging.error("update_dashboard failed: %s", error)
        finally:
            self.after(Config.REFRESH_MS, self.update_dashboard)

    def _update_dashboard_impl(self):
        now = datetime.now()
        self.clock.config(text=now.strftime("%H:%M:%S"))
        self.date.config(text=now.strftime("%A, %d %B %Y"))

        self.hostname.config(text=safe(socket.gethostname, "Unavailable", "hostname"))
        self.ip.config(text=safe(get_local_ip, "Unavailable", "ip"))

        self._update_uptime()
        self._update_loadavg()
        self._update_cpu()
        self._update_ram()
        self._update_disk()
        self._update_network()
        self._update_swap()
        self._update_temperature()
        self._update_processes()

    def _update_uptime(self):
        def calc():
            seconds = int(time.time() - psutil.boot_time())
            d, rem = divmod(seconds, 86400)
            h, rem = divmod(rem, 3600)
            m, _ = divmod(rem, 60)
            return f"{d}d {h}h {m}m"
        self.uptime.config(text=safe(calc, "Unavailable", "uptime"))

    def _update_loadavg(self):
        def calc():
            one, five, fifteen = os.getloadavg()
            return f"{one:.2f} / {five:.2f} / {fifteen:.2f}"
        self.loadavg.config(text=safe(calc, "N/A", "loadavg"))

    def _update_cpu(self):
        overall = safe(lambda: psutil.cpu_percent(interval=None), 0, "cpu overall")
        per_core = safe(lambda: psutil.cpu_percent(interval=None, percpu=True), [], "cpu percore")

        self._set_resource(self.cpu, overall, detail=f"{psutil.cpu_count()} cores")
        self._update_core_bars(per_core)

    def _update_core_bars(self, per_core):
        panel = self.cpu
        # (Re)build core bars once, or if core count changed. Bars wrap into
        # a fixed-column grid (rather than one row per core) so the panel's
        # height stays bounded even on servers with many cores.
        if len(panel["core_bars"]) != len(per_core):
            for widget in panel["cores_frame"].winfo_children():
                widget.destroy()
            panel["core_bars"] = []

            columns = min(max(len(per_core), 1), 16)
            for col in range(columns):
                panel["cores_frame"].grid_columnconfigure(col, weight=1, uniform="cores")

            for idx in range(len(per_core)):
                row, col = divmod(idx, columns)
                bar_bg = tk.Frame(panel["cores_frame"], bg="#222222", height=5)
                bar_bg.grid(row=row, column=col, sticky="ew", padx=1, pady=1)
                bar = tk.Frame(bar_bg, bg=GREEN, height=5)
                bar.place(x=0, y=0, relheight=1, relwidth=0)
                panel["core_bars"].append(bar)

        for bar, pct in zip(panel["core_bars"], per_core):
            bar.config(bg=status_color(pct))
            bar.place(relwidth=max(0, min(pct / 100, 1)), relheight=1)

    def _update_ram(self):
        def calc():
            vm = psutil.virtual_memory()
            return vm.percent, f"{format_bytes(vm.used)} / {format_bytes(vm.total)}"
        result = safe(calc, (0, ""), "ram")
        percent, detail = result if result else (0, "")
        self._set_resource(self.ram, percent, detail=detail)

    def _update_disk(self):
        def calc():
            du = psutil.disk_usage(Config.DISK_PATH)
            return du.percent, f"{format_bytes(du.used)} / {format_bytes(du.total)}"
        result = safe(calc, (0, ""), "disk")
        percent, detail = result if result else (0, "")
        self._set_resource(self.disk, percent, detail=detail)

    def _set_resource(self, panel, percent, detail=""):
        percent = percent or 0
        color = status_color(percent)
        panel["value"].config(text=f"{percent:.0f}%", fg=color)
        panel["detail"].config(text=detail)
        panel["bar"].config(bg=color)
        panel["bar"].place(relwidth=max(0, min(percent / 100, 1)), relheight=1)
        panel["spark"].color = color
        panel["spark"].push(percent)

    def _update_network(self):
        def calc():
            counters = psutil.net_io_counters()
            now = time.time()
            elapsed = max(now - self._last_sample_time, 0.001)

            sent_rate = (counters.bytes_sent - self._last_net.bytes_sent) / elapsed
            recv_rate = (counters.bytes_recv - self._last_net.bytes_recv) / elapsed

            self._last_net = counters
            self._last_sample_time = now

            return f"\u2191 {format_bytes_per_sec(sent_rate)}\n\u2193 {format_bytes_per_sec(recv_rate)}"

        self.network.config(text=safe(calc, "Unavailable", "network"))

    def _update_swap(self):
        def calc():
            sw = psutil.swap_memory()
            if sw.total == 0:
                return "No swap configured"
            return f"{sw.percent:.0f}%\n{format_bytes(sw.used)} / {format_bytes(sw.total)}"
        self.swap.config(text=safe(calc, "Unavailable", "swap"))

    def _update_temperature(self):
        def calc():
            sensors = psutil.sensors_temperatures()
            if not sensors:
                return "No sensors found"
            # Grab the first available sensor reading
            for name, entries in sensors.items():
                for entry in entries:
                    if entry.current:
                        return f"{entry.current:.0f}\u00b0C\n({entry.label or name})"
            return "No sensors found"
        self.temp.config(text=safe(calc, "Not supported", "temperature"))

    def _update_processes(self):
        def calc():
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    procs.append(p.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            procs.sort(key=lambda p: p["cpu_percent"] or 0, reverse=True)
            return procs[: Config.TOP_PROCESS_COUNT]

        top = safe(calc, [], "processes")
        for i, row in enumerate(self.process_labels):
            if i < len(top):
                p = top[i]
                row["name"].config(text=(p["name"] or "?")[:28])
                row["cpu"].config(text=f"{p['cpu_percent']:.1f}% cpu")
                row["mem"].config(text=f"{p['memory_percent']:.1f}% mem")
            else:
                row["name"].config(text="\u2014")
                row["cpu"].config(text="")
                row["mem"].config(text="")

    # ========================================================
    # IDLE / SCREENSAVER
    # ========================================================

    def user_activity(self, event=None):
        self.last_activity = time.time()
        if self.screensaver_active:
            self.hide_screensaver()

    def check_idle(self):
        idle_time = time.time() - self.last_activity
        if idle_time >= Config.IDLE_SECONDS and not self.screensaver_active:
            self.show_screensaver()
        self.after(1000, self.check_idle)

    def show_screensaver(self):
        self.screensaver_active = True

        self.screensaver = tk.Frame(self, bg="black")
        self.screensaver.place(x=0, y=0, relwidth=1, relheight=1)

        self._load_screensaver_image()

        self.saver_clock = tk.Label(
            self.screensaver, text="", bg="#000000", fg=RED, font=("Segoe UI", 46, "bold")
        )
        self.saver_clock.place(relx=0.5, rely=0.85, anchor="center")

        self.saver_stats = tk.Label(
            self.screensaver, text="", bg="#000000", fg=DIM, font=("Segoe UI", 13),
            justify="center"
        )
        self.saver_stats.place(relx=0.5, rely=0.93, anchor="center")

        self.update_screensaver()
        self.screensaver.focus_set()

    def _load_screensaver_image(self):
        if not PIL_AVAILABLE:
            self._screensaver_fallback_label("PIL/Pillow not installed")
            return

        if not os.path.exists(Config.SCREENSAVER_IMAGE):
            self._screensaver_fallback_label("SCREENSAVER IMAGE NOT FOUND")
            return

        try:
            image = Image.open(Config.SCREENSAVER_IMAGE)
            screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
            img_w, img_h = image.size

            scale = max(screen_w / img_w, screen_h / img_h)
            new_w, new_h = int(img_w * scale), int(img_h * scale)
            image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

            left = (new_w - screen_w) // 2
            top = (new_h - screen_h) // 2
            image = image.crop((left, top, left + screen_w, top + screen_h))

            self.screensaver_image = ImageTk.PhotoImage(image)
            tk.Label(
                self.screensaver, image=self.screensaver_image, bg="black"
            ).place(x=0, y=0, relwidth=1, relheight=1)

        except Exception as error:
            logging.warning("Could not load screensaver image: %s", error)
            self._screensaver_fallback_label("SCREENSAVER IMAGE NOT FOUND")

    def _screensaver_fallback_label(self, text):
        tk.Label(
            self.screensaver, text=text, bg="black", fg=RED, font=("Segoe UI", 28, "bold")
        ).place(relx=0.5, rely=0.5, anchor="center")

    def update_screensaver(self):
        if not self.screensaver_active:
            return

        self.saver_clock.config(text=datetime.now().strftime("%H:%M:%S"))

        cpu = safe(lambda: psutil.cpu_percent(interval=None), 0, "saver cpu")
        ram = safe(lambda: psutil.virtual_memory().percent, 0, "saver ram")
        self.saver_stats.config(text=f"CPU {cpu:.0f}%   \u00b7   MEM {ram:.0f}%")

        self.after(1000, self.update_screensaver)

    def hide_screensaver(self):
        self.screensaver_active = False
        if hasattr(self, "screensaver"):
            self.screensaver.destroy()
        self.last_activity = time.time()


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":
    try:
        app = Dashboard()
        app.mainloop()
    except Exception as e:
        logging.exception("Fatal dashboard error")
        print("\n" + "=" * 60)
        print("DASHBOARD ERROR")
        print("=" * 60)
        print(f"{type(e).__name__}: {e}")
        print(f"See {Config.LOG_FILE} for details")
        print("=" * 60 + "\n")
        raise
