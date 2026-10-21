"""Wires the pieces together. Tk owns the main thread; everything else posts to self.q."""
import logging
import os
import queue
import time
import tkinter as tk
from tkinter import messagebox

from . import winapi
from .config import Config, data_dir
from .monitor import Monitor
from .presence import State
from .profile_store import ProfileStore
from .ui.countdown import Countdown
from .ui.diagnostics import DiagnosticsWindow
from .ui.enroll import EnrollWindow
from .ui.settings import SettingsWindow
from .ui.tray import Tray

log = logging.getLogger(__name__)


def _fmt_minutes(seconds):
    if seconds is None:
        return ""
    if seconds == float("inf"):
        return " until resumed"
    return f" for {max(1, round(seconds / 60))} min"


class App:
    def __init__(self):
        self.cfg = Config()
        self.store = ProfileStore()
        self.q = queue.Queue()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("FaceLock")
        self.window = None          # the one open Enroll/Diagnostics/Settings window
        self.last_state = None
        self._quitting = False
        self.monitor = Monitor(self.cfg, self.store,
                               on_status=lambda s: self.q.put(("status", s)),
                               on_notify=lambda m: self.q.put(("notify", m)))
        self.events = winapi.SessionEvents(self._on_session_event)
        self.tray = Tray(self)
        self.countdown = Countdown(self.root, on_cancel=self._cancel_countdown,
                                   show_cancel=self.cfg["dev_mode"])

    # -- thread-safe entry points ---------------------------------------------

    def call(self, fn, *args):
        self.q.put(("call", (fn, args)))

    def _on_session_event(self, event):
        self.monitor.post("session", event)
        if event == "endsession":
            self.q.put(("call", (self.quit, ())))

    # -- Tk thread ------------------------------------------------------------

    def run(self):
        self.events.start()
        self.tray.start()
        self.monitor.start()
        if not self.store.exists():
            self.tray.notify("Welcome! Enroll your face to start auto-locking.")
            self.root.after(800, lambda: self.open_enroll(False))
        self.root.after(100, self._poll)
        self.root.mainloop()

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "status":
                    self._show_status(payload)
                elif kind == "notify":
                    self.tray.notify(payload)
                elif kind == "call":
                    fn, args = payload
                    try:
                        fn(*args)
                    except Exception:
                        log.exception("UI action failed")
        except queue.Empty:
            pass
        if not self._quitting:
            self.root.after(100, self._poll)

    def _show_status(self, s):
        state = s["state"]
        text = state.value
        if state is State.PAUSED:
            text += s["detail"] and f" ({s['detail']})" or _fmt_minutes(s["paused_for"])
        elif state is State.CAMERA_BUSY and s["detail"]:
            text += f": {s['detail']}"
        elif state is State.COUNTDOWN and s["remaining"] is not None:
            text = f"Locking in {s['remaining']:.0f} s"
        elif state is State.PRESENT and s["score"] is not None:
            text += f" (match {s['score']:.2f})"
        self.tray.update(state, text)
        if state is State.COUNTDOWN and s["remaining"] is not None:
            self.countdown.show(s["remaining"])
        else:
            self.countdown.hide()
        if state is State.CAMERA_BUSY and self.last_state is not State.CAMERA_BUSY:
            self.tray.notify("Camera is in use by another app - monitoring paused until it is free.")
        self.last_state = state

    def _cancel_countdown(self):
        minutes = self.cfg["cancel_pause_min"]
        log.info("countdown cancelled - pausing %d min", minutes)
        self.pause(minutes * 60)

    def pause(self, seconds):
        self.monitor.post("pause", seconds)

    def resume(self):
        self.monitor.post("resume")

    def _open(self, factory):
        if self.window is not None:
            try:
                self.window.win.lift()
                self.window.win.focus_force()
                return
            except tk.TclError:
                self.window = None
        self.window = factory()
        self.window.win.lift()
        self.window.win.focus_force()

    def _closed(self):
        self.window = None

    def open_enroll(self, improve):
        if improve and not self.store.exists():
            improve = False  # nothing to improve yet: do the basic enrollment first
        self._open(lambda: EnrollWindow(self.root, self.cfg, self.store, self.monitor, improve, self._closed))

    def open_diagnostics(self):
        self._open(lambda: DiagnosticsWindow(self.root, self.cfg, self.store, self.monitor, self._closed))

    def open_settings(self):
        self._open(lambda: SettingsWindow(self.root, self.cfg, self._settings_saved, self._closed))

    def _settings_saved(self):
        self.countdown.set_show_cancel(self.cfg["dev_mode"])
        self.monitor.post("reload_config")

    def delete_profile(self):
        if messagebox.askyesno("FaceLock", "Delete your enrolled face data?\n"
                               "Auto-lock stops until you enroll again."):
            self.store.delete()
            self.monitor.post("reload_profile")

    def open_log_folder(self):
        os.startfile(data_dir())

    def quit(self):
        if self._quitting:
            return
        self._quitting = True
        log.info("quitting")
        self.countdown.hide()
        self.monitor.stop()
        self.events.stop()
        self.tray.stop()
        self.monitor.join(3)
        self.root.destroy()
