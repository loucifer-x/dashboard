#!/usr/bin/env python3
"""
Proxmox-style dashboard - Tkinter GUI
Black background, red accents. Sidebar with nodes/VMs/containers,
a summary panel with usage bars, and a resource list.
Pure stdlib (tkinter) - no extra installs needed.
"""

import tkinter as tk
from tkinter import ttk

BG = "#0a0a0a"
PANEL = "#150707"
BORDER = "#3a1414"
RED = "#c23b3b"
RED_BRIGHT = "#ff5050"
DIM = "#8a6060"
TEXT = "#e0a0a0"
GREEN = "#4ade80"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_MONO = ("Consolas", 10)

VMS = [
    {"id": 100, "name": "pfsense",    "type": "VM", "status": "running", "cpu": 12, "mem": 34},
    {"id": 101, "name": "ubuntu-srv", "type": "VM", "status": "running", "cpu": 47, "mem": 68},
    {"id": 102, "name": "win11-vm",   "type": "VM", "status": "stopped", "cpu": 0,  "mem": 0},
    {"id": 200, "name": "docker-host","type": "CT", "status": "running", "cpu": 25, "mem": 52},
    {"id": 201, "name": "adguard",    "type": "CT", "status": "running", "cpu": 3,  "mem": 15},
    {"id": 202, "name": "test-ct",    "type": "CT", "status": "stopped", "cpu": 0,  "mem": 0},
]


class Bar(tk.Canvas):
    """Simple horizontal usage bar."""
    def __init__(self, master, pct, width=140, height=10, **kw):
        super().__init__(master, width=width, height=height, bg=PANEL,
                          highlightthickness=0, **kw)
        self.create_rectangle(0, 0, width, height, fill="#2a1010", outline="")
        fill_w = max(2, int(width * pct / 100))
        color = RED_BRIGHT if pct < 80 else "#ff8080"
        self.create_rectangle(0, 0, fill_w, height, fill=color, outline="")


class Sidebar(tk.Frame):
    def __init__(self, master, on_select):
        super().__init__(master, bg=PANEL, width=200)
        self.pack_propagate(False)
        self.on_select = on_select

        tk.Label(self, text="PVE01", bg=PANEL, fg=RED_BRIGHT,
                 font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", padx=14, pady=(16, 4))
        tk.Label(self, text="Proxmox VE 8.3", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=14, pady=(0, 16))

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x", padx=0, pady=(0, 8))

        self.buttons = {}
        for label in ("Dashboard", "Virtual Machines", "Containers", "Storage", "Settings"):
            b = tk.Label(self, text=label, bg=PANEL, fg=TEXT, font=FONT,
                         anchor="w", padx=14, pady=8, cursor="hand2")
            b.pack(fill="x")
            b.bind("<Enter>", lambda e, w=b: w.configure(bg="#241010"))
            b.bind("<Leave>", lambda e, w=b: w.configure(bg=PANEL) if w != self.active else None)
            b.bind("<Button-1>", lambda e, l=label: self._select(l))
            self.buttons[label] = b

        self.active = None
        self._select("Dashboard")

    def _select(self, label):
        if self.active:
            self.active.configure(bg=PANEL, fg=TEXT)
        b = self.buttons[label]
        b.configure(bg="#2a0f0f", fg=RED_BRIGHT)
        self.active = b
        self.on_select(label)


class Dashboard(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG)

        tk.Label(self, text="Node summary", bg=BG, fg=RED_BRIGHT,
                 font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=20, pady=(18, 10))

        stats = tk.Frame(self, bg=BG)
        stats.pack(fill="x", padx=20, pady=(0, 16))
        for label, value in (("CPU usage", "38%"), ("Memory", "22.4 / 64 GB"),
                              ("Storage", "1.1 / 4 TB"), ("Uptime", "14d 6h")):
            card = tk.Frame(stats, bg=PANEL, bd=1, relief="flat",
                             highlightbackground=BORDER, highlightthickness=1)
            card.pack(side="left", expand=True, fill="both", padx=(0, 10))
            tk.Label(card, text=label, bg=PANEL, fg=DIM, font=("Segoe UI", 8),
                      anchor="w").pack(fill="x", padx=12, pady=(10, 0))
            tk.Label(card, text=value, bg=PANEL, fg=TEXT, font=("Segoe UI", 14, "bold"),
                      anchor="w").pack(fill="x", padx=12, pady=(0, 12))

        tk.Label(self, text="Guests", bg=BG, fg=RED_BRIGHT,
                 font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=20, pady=(6, 6))

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=20)
        cols = [("VMID", 60), ("Name", 160), ("Type", 60), ("Status", 90), ("CPU", 150), ("Mem", 150)]
        for text, w in cols:
            tk.Label(header, text=text, bg=BG, fg=DIM, font=("Segoe UI", 8, "bold"),
                      width=int(w / 8), anchor="w").pack(side="left", padx=(0, 4))

        rows_frame = tk.Frame(self, bg=BG)
        rows_frame.pack(fill="both", expand=True, padx=20, pady=(4, 16))

        for row in VMS:
            r = tk.Frame(rows_frame, bg=PANEL, highlightbackground=BORDER,
                         highlightthickness=1)
            r.pack(fill="x", pady=2)

            tk.Label(r, text=row["id"], bg=PANEL, fg=TEXT, font=FONT_MONO,
                      width=7, anchor="w").pack(side="left", padx=(8, 0), pady=6)
            tk.Label(r, text=row["name"], bg=PANEL, fg=TEXT, font=FONT,
                      width=20, anchor="w").pack(side="left")
            tk.Label(r, text=row["type"], bg=PANEL, fg=DIM, font=FONT,
                      width=7, anchor="w").pack(side="left")

            status_color = GREEN if row["status"] == "running" else DIM
            tk.Label(r, text=row["status"], bg=PANEL, fg=status_color, font=FONT,
                      width=11, anchor="w").pack(side="left")

            cpu_frame = tk.Frame(r, bg=PANEL, width=150)
            cpu_frame.pack(side="left", padx=4)
            Bar(cpu_frame, row["cpu"]).pack(pady=8)

            mem_frame = tk.Frame(r, bg=PANEL, width=150)
            mem_frame.pack(side="left", padx=4)
            Bar(mem_frame, row["mem"]).pack(pady=8)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Proxmox Dashboard")
        self.geometry("880x560")
        self.configure(bg=BG)
        self.minsize(760, 460)

        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True)

        self.body = tk.Frame(container, bg=BG)
        self.sidebar = Sidebar(container, self._on_nav)
        self.sidebar.pack(side="left", fill="y")
        self.body.pack(side="left", fill="both", expand=True)

        self.dashboard = Dashboard(self.body)
        self.dashboard.pack(fill="both", expand=True)

        self.placeholder = tk.Label(self.body, text="", bg=BG, fg=DIM, font=("Segoe UI", 12))

    def _on_nav(self, label):
        for w in self.body.winfo_children():
            w.pack_forget()
        if label == "Dashboard":
            self.dashboard.pack(fill="both", expand=True)
        else:
            self.placeholder.configure(text=f"{label} - not wired up in this demo")
            self.placeholder.pack(fill="both", expand=True, pady=40)


if __name__ == "__main__":
    App().mainloop()
