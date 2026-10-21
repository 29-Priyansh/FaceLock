import tkinter as tk
from tkinter import messagebox

FIELDS = [
    # key, label, type, min, max
    ("lock_after_s", "Lock after not seeing you for (seconds)", int, 5, 300),
    ("sample_interval_s", "Check interval while you are present (seconds)", float, 1.0, 30.0),
    ("match_threshold", "Match threshold (higher = stricter)", float, 0.2, 0.9),
    ("camera_index", "Camera index", int, 0, 9),
    ("cancel_pause_min", "Cancel pauses monitoring for (minutes)", int, 1, 240),
]


class SettingsWindow:
    def __init__(self, root, cfg, on_saved, on_close=None):
        self.cfg, self.on_saved, self.on_close = cfg, on_saved, on_close
        win = self.win = tk.Toplevel(root)
        win.title("FaceLock - Settings")
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self.close)
        self.vars = {}
        for row, (key, label, _, lo, hi) in enumerate(FIELDS):
            tk.Label(win, text=f"{label}  [{lo}-{hi}]").grid(row=row, column=0, sticky="w", padx=10, pady=4)
            var = tk.StringVar(value=str(cfg[key]))
            tk.Entry(win, textvariable=var, width=10).grid(row=row, column=1, padx=10, pady=4)
            self.vars[key] = var
        self.dev = tk.BooleanVar(value=cfg["dev_mode"])
        tk.Checkbutton(win, text="Developer mode (show Cancel on the countdown)", variable=self.dev).grid(
            row=len(FIELDS), column=0, columnspan=2, sticky="w", padx=10, pady=4)
        bar = tk.Frame(win)
        bar.grid(row=len(FIELDS) + 1, column=0, columnspan=2, pady=10)
        tk.Button(bar, text="Save", width=10, command=self.save).pack(side="left", padx=4)
        tk.Button(bar, text="Cancel", width=10, command=self.close).pack(side="left", padx=4)

    def save(self):
        values = {}
        for key, label, typ, lo, hi in FIELDS:
            try:
                v = typ(self.vars[key].get())
            except ValueError:
                messagebox.showerror("FaceLock", f"Invalid value for: {label}", parent=self.win)
                return
            if not lo <= v <= hi:
                messagebox.showerror("FaceLock", f"{label} must be between {lo} and {hi}", parent=self.win)
                return
            values[key] = v
        self.cfg.update(values)
        self.cfg["dev_mode"] = bool(self.dev.get())
        self.cfg.save()
        self.on_saved()
        self.close()

    def close(self):
        self.win.destroy()
        if self.on_close:
            self.on_close()
