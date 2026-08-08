
import tkinter as tk
from datetime import datetime


class Clock(tk.Tk):
    def __init__(self):
        super().__init__()

        # Window
        self.title("Server Dashboard")
        self.configure(bg="#111111")
        self.attributes("-fullscreen", True)

        # Allow Escape to exit fullscreen
        self.bind("<Escape>", self.exit_fullscreen)

        # Time
        self.time_label = tk.Label(
            self,
            text="",
            bg="#111111",
            fg="white",
            font=("Segoe UI", 80, "bold")
        )
        self.time_label.pack(expand=True, pady=(100, 0))

        # Date
        self.date_label = tk.Label(
            self,
            text="",
            bg="#111111",
            fg="#888888",
            font=("Segoe UI", 22)
        )
        self.date_label.pack(pady=(0, 150))

        # Start clock
        self.update_clock()

    def update_clock(self):
        now = datetime.now()

        self.time_label.config(
            text=now.strftime("%H:%M:%S")
        )

        self.date_label.config(
            text=now.strftime("%A, %d %B %Y")
        )

        # Update every second
        self.after(1000, self.update_clock)

    def exit_fullscreen(self, event=None):
        self.attributes("-fullscreen", False)


if __name__ == "__main__":
    app = Clock()
    app.mainloop()

