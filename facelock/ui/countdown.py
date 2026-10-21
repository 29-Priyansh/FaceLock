"""Small topmost "Locking in N" overlay that never takes keyboard focus."""
import tkinter as tk

from .. import winapi

BG = "#202124"
FG = "#ffffff"
ACCENT = "#f0a020"


class Countdown:
    def __init__(self, root, on_cancel, show_cancel):
        self.on_cancel = on_cancel
        self.visible = False
        top = self.top = tk.Toplevel(root)
        top.withdraw()
        top.overrideredirect(True)
        top.configure(bg=BG, highlightthickness=1, highlightbackground=ACCENT)
        self.title = tk.Label(top, text="Locking in 10", font=("Segoe UI", 18, "bold"), fg=ACCENT, bg=BG)
        self.title.pack(padx=18, pady=(12, 0))
        tk.Label(top, text="Look at the camera to stay unlocked", font=("Segoe UI", 9),
                 fg=FG, bg=BG).pack(padx=18, pady=(2, 10))
        self.cancel_btn = tk.Button(top, text="Cancel (pause monitoring)", command=self._cancel,
                                    font=("Segoe UI", 9), relief="flat", bg="#3c4043", fg=FG,
                                    activebackground="#5f6368", activeforeground=FG, takefocus=0)
        self.set_show_cancel(show_cancel)
        top.update_idletasks()
        self.hwnd = winapi.toplevel_hwnd(top)
        winapi.make_no_activate(self.hwnd)
        # Map once off-screen so Tk considers the window shown; afterwards visibility is
        # switched with ShowWindow(SW_SHOWNOACTIVATE / SW_HIDE) so focus is never taken.
        top.geometry("+-10000+-10000")
        top.deiconify()
        top.update_idletasks()
        winapi.hide_window(self.hwnd)

    def set_show_cancel(self, show):
        if show:
            self.cancel_btn.pack(padx=18, pady=(0, 12), fill="x")
        else:
            self.cancel_btn.pack_forget()

    def _cancel(self):
        self.hide()
        self.on_cancel()

    def show(self, remaining):
        self.title.config(text=f"Locking in {max(0, int(remaining + 0.999))}")
        if not self.visible:
            top = self.top
            top.update_idletasks()
            w, h = top.winfo_reqwidth(), top.winfo_reqheight()
            x = top.winfo_screenwidth() - w - 24
            y = top.winfo_screenheight() - h - 72  # stay above the taskbar
            top.geometry(f"{w}x{h}+{x}+{y}")
            top.update_idletasks()
            winapi.show_no_activate(self.hwnd)
            self.visible = True

    def hide(self):
        if self.visible:
            winapi.hide_window(self.hwnd)
            self.visible = False
