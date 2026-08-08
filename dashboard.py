
import tkinter as tk
import socket
import time
from datetime import datetime

import psutil
from PIL import Image, ImageTk


# ============================================================
# SETTINGS
# ============================================================

BG = "#050505"
PANEL = "#0d0d0d"

RED = "#ff2020"
DARK_RED = "#8b0000"
RED_DIM = "#b30000"

TEXT = "#ffffff"
DIM = "#777777"

# Seconds of inactivity before screensaver
IDLE_TIME = 1

# Screensaver image
IMAGE_PATH = "/root/dashboard/images.jpg"


class Dashboard(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("Server Dashboard")

        # Fullscreen
        self.attributes("-fullscreen", True)

        self.configure(bg=BG)

        # Screensaver state
        self.screensaver_active = False
        self.last_activity = time.time()

        self.screensaver_image = None

        # ----------------------------------------------------
        # Detect mouse / keyboard activity
        # ----------------------------------------------------

        self.bind_all("<Motion>", self.user_activity)
        self.bind_all("<Key>", self.user_activity)
        self.bind_all("<Button>", self.user_activity)

        # ----------------------------------------------------
        # Build dashboard
        # ----------------------------------------------------

        self.create_ui()

        # ----------------------------------------------------
        # Start updates
        # ----------------------------------------------------

        self.update_dashboard()
        self.check_idle()

    # ========================================================
    # DASHBOARD UI
    # ========================================================

    def create_ui(self):

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        header = tk.Frame(
            self,
            bg=BG
        )

        header.pack(
            fill="x",
            padx=45,
            pady=(30, 15)
        )

        title = tk.Label(
            header,
            text="SERVER DASHBOARD",
            bg=BG,
            fg=RED,
            font=("Segoe UI", 30, "bold")
        )

        title.pack(side="left")

        self.clock = tk.Label(
            header,
            text="00:00:00",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 26, "bold")
        )

        self.clock.pack(side="right")

        self.date = tk.Label(
            header,
            text="",
            bg=BG,
            fg=DIM,
            font=("Segoe UI", 11)
        )

        self.date.pack(
            side="right",
            padx=(0, 25)
        )

        # ----------------------------------------------------
        # Red separator
        # ----------------------------------------------------

        separator = tk.Frame(
            self,
            bg=RED,
            height=2
        )

        separator.pack(
            fill="x",
            padx=45
        )

        # ----------------------------------------------------
        # Server information
        # ----------------------------------------------------

        info = tk.Frame(
            self,
            bg=BG
        )

        info.pack(
            fill="x",
            padx=40,
            pady=25
        )

        self.hostname = self.create_info(
            info,
            "HOSTNAME"
        )

        self.ip = self.create_info(
            info,
            "IP ADDRESS"
        )

        self.uptime = self.create_info(
            info,
            "UPTIME"
        )

        # ----------------------------------------------------
        # Resource panels
        # ----------------------------------------------------

        resources = tk.Frame(
            self,
            bg=BG
        )

        resources.pack(
            fill="both",
            expand=True,
            padx=40,
            pady=10
        )

        self.cpu = self.create_resource_panel(
            resources,
            "CPU USAGE"
        )

        self.ram = self.create_resource_panel(
            resources,
            "MEMORY"
        )

        self.disk = self.create_resource_panel(
            resources,
            "DISK"
        )

        # ----------------------------------------------------
        # Footer
        # ----------------------------------------------------

        footer = tk.Frame(
            self,
            bg=BG
        )

        footer.pack(
            fill="x",
            padx=45,
            pady=25
        )

        self.status = tk.Label(
            footer,
            text="● SYSTEM ONLINE",
            bg=BG,
            fg=RED,
            font=("Segoe UI", 12, "bold")
        )

        self.status.pack(side="left")

        hint = tk.Label(
            footer,
            text="AFK SCREENSAVER: 60s",
            bg=BG,
            fg=DIM,
            font=("Segoe UI", 9)
        )

        hint.pack(side="right")

    # ========================================================
    # INFO CARD
    # ========================================================

    def create_info(self, parent, title):

        frame = tk.Frame(
            parent,
            bg=PANEL,
            highlightbackground=DARK_RED,
            highlightthickness=1
        )

        frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=6
        )

        title_label = tk.Label(
            frame,
            text=title,
            bg=PANEL,
            fg=RED_DIM,
            font=("Segoe UI", 9, "bold")
        )

        title_label.pack(
            anchor="w",
            padx=20,
            pady=(15, 3)
        )

        value_label = tk.Label(
            frame,
            text="Loading...",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 16, "bold")
        )

        value_label.pack(
            anchor="w",
            padx=20,
            pady=(0, 15)
        )

        return value_label

    # ========================================================
    # RESOURCE CARD
    # ========================================================

    def create_resource_panel(self, parent, title):

        frame = tk.Frame(
            parent,
            bg=PANEL,
            highlightbackground=DARK_RED,
            highlightthickness=1
        )

        frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=8
        )

        title_label = tk.Label(
            frame,
            text=title,
            bg=PANEL,
            fg=RED_DIM,
            font=("Segoe UI", 12, "bold")
        )

        title_label.pack(
            anchor="w",
            padx=25,
            pady=(25, 5)
        )

        value = tk.Label(
            frame,
            text="0%",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 46, "bold")
        )

        value.pack(
            pady=25
        )

        bar_background = tk.Frame(
            frame,
            bg="#222222",
            height=10
        )

        bar_background.pack(
            fill="x",
            padx=25
        )

        bar = tk.Frame(
            bar_background,
            bg=RED,
            height=10
        )

        bar.place(
            x=0,
            y=0,
            relheight=1,
            relwidth=0
        )

        return {
            "value": value,
            "bar": bar
        }

    # ========================================================
    # UPDATE DASHBOARD
    # ========================================================

    def update_dashboard(self):

        now = datetime.now()

        # Clock
        self.clock.config(
            text=now.strftime("%H:%M:%S")
        )

        # Date
        self.date.config(
            text=now.strftime("%A, %d %B %Y")
        )

        # Hostname
        self.hostname.config(
            text=socket.gethostname()
        )

        # IP address
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
        except Exception:
            ip = "Unavailable"

        self.ip.config(
            text=ip
        )

        # Uptime
        uptime_seconds = int(
            time.time() - psutil.boot_time()
        )

        days = uptime_seconds // 86400

        hours = (
            uptime_seconds % 86400
        ) // 3600

        minutes = (
            uptime_seconds % 3600
        ) // 60

        self.uptime.config(
            text=f"{days}d {hours}h {minutes}m"
        )

        # CPU
        cpu = psutil.cpu_percent(
            interval=None
        )

        self.update_resource(
            self.cpu,
            cpu
        )

        # RAM
        ram = psutil.virtual_memory().percent

        self.update_resource(
            self.ram,
            ram
        )

        # Disk
        disk = psutil.disk_usage("/").percent

        self.update_resource(
            self.disk,
            disk
        )

        # Run again in one second
        self.after(
            1000,
            self.update_dashboard
        )

    # ========================================================
    # RESOURCE UPDATE
    # ========================================================

    def update_resource(
        self,
        resource,
        percentage
    ):

        resource["value"].config(
            text=f"{percentage:.0f}%"
        )

        resource["bar"].place(
            relwidth=max(
                0,
                min(
                    percentage / 100,
                    1
                )
            ),
            relheight=1
        )

    # ========================================================
    # USER ACTIVITY
    # ========================================================

    def user_activity(self, event=None):

        self.last_activity = time.time()

        if self.screensaver_active:
            self.hide_screensaver()

    # ========================================================
    # CHECK IDLE
    # ========================================================

    def check_idle(self):

        idle_time = time.time() - self.last_activity

        if (
            idle_time >= IDLE_TIME
            and not self.screensaver_active
        ):
            self.show_screensaver()

        self.after(
            1000,
            self.check_idle
        )

    # ========================================================
    # SHOW SCREENSAVER
    # ========================================================

    def show_screensaver(self):

        self.screensaver_active = True

        # Fullscreen black background
        self.screensaver = tk.Frame(
            self,
            bg="black"
        )

        self.screensaver.place(
            x=0,
            y=0,
            relwidth=1,
            relheight=1
        )

        # ----------------------------------------------------
        # Load wallpaper
        # ----------------------------------------------------

        try:

            image = Image.open(
                IMAGE_PATH
            )

            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()

            # ------------------------------------------------
            # Scale image so it fills the entire screen
            # while keeping its aspect ratio.
            # ------------------------------------------------

            image_width, image_height = image.size

            scale = max(
                screen_width / image_width,
                screen_height / image_height
            )

            new_width = int(
                image_width * scale
            )

            new_height = int(
                image_height * scale
            )

            image = image.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )

            # ------------------------------------------------
            # Crop to screen
            # ------------------------------------------------

            left = (
                new_width - screen_width
            ) // 2

            top = (
                new_height - screen_height
            ) // 2

            right = left + screen_width
            bottom = top + screen_height

            image = image.crop(
                (
                    left,
                    top,
                    right,
                    bottom
                )
            )

            self.screensaver_image = ImageTk.PhotoImage(
                image
            )

            image_label = tk.Label(
                self.screensaver,
                image=self.screensaver_image,
                bg="black"
            )

            image_label.place(
                x=0,
                y=0,
                relwidth=1,
                relheight=1
            )

        except Exception as error:

            print(
                f"Could not load {IMAGE_PATH}: {error}"
            )

            image_label = tk.Label(
                self.screensaver,
                text="SCREENSAVER IMAGE NOT FOUND",
                bg="black",
                fg=RED,
                font=("Segoe UI", 30, "bold")
            )

            image_label.place(
                relx=0.5,
                rely=0.5,
                anchor="center"
            )

        # ----------------------------------------------------
        # Screensaver clock
        # ----------------------------------------------------

        self.saver_clock = tk.Label(
            self.screensaver,
            text="",
            bg="#000000",
            fg=RED,
            font=("Segoe UI", 50, "bold")
        )

        self.saver_clock.place(
            relx=0.5,
            rely=0.9,
            anchor="center"
        )

        self.update_screensaver_clock()

        # Make sure the screensaver receives keyboard input
        self.screensaver.focus_set()

    # ========================================================
    # SCREENSAVER CLOCK
    # ========================================================

    def update_screensaver_clock(self):

        if not self.screensaver_active:
            return

        self.saver_clock.config(
            text=datetime.now().strftime("%H:%M:%S")
        )

        self.after(
            1000,
            self.update_screensaver_clock
        )

    # ========================================================
    # HIDE SCREENSAVER
    # ========================================================

    def hide_screensaver(self):

        self.screensaver_active = False

        if hasattr(
            self,
            "screensaver"
        ):
            self.screensaver.destroy()

        self.last_activity = time.time()


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    app = Dashboard()

    app.mainloop()

