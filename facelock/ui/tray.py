"""System-tray icon. pystray runs its own Win32 loop on a background thread;
every menu action is forwarded to the Tk thread through app.call()."""
import pystray
from pystray import Menu, MenuItem as Item

from .. import APP_NAME
from ..presence import State
from .icons import STATE_COLOR, make_icon


class Tray:
    def __init__(self, app):
        self.app = app
        self.status_text = "Starting..."
        self.state = None
        self._icons = {}
        a = app.call
        pause = Menu(
            Item("5 minutes", lambda: a(app.pause, 5 * 60)),
            Item("30 minutes", lambda: a(app.pause, 30 * 60)),
            Item("1 hour", lambda: a(app.pause, 60 * 60)),
            Item("Until I resume", lambda: a(app.pause, None)),
        )
        menu = Menu(
            Item(lambda _: self.status_text, None, enabled=False),
            Menu.SEPARATOR,
            Item("Pause monitoring", pause, visible=lambda _: self.state is not State.PAUSED),
            Item("Resume monitoring", lambda: a(app.resume), visible=lambda _: self.state is State.PAUSED),
            Menu.SEPARATOR,
            Item("Improve face recognition...", lambda: a(app.open_enroll, True)),
            Item("Enroll face (start over)...", lambda: a(app.open_enroll, False)),
            Item("Delete face data...", lambda: a(app.delete_profile)),
            Menu.SEPARATOR,
            Item("Diagnostics...", lambda: a(app.open_diagnostics)),
            Item("Settings...", lambda: a(app.open_settings)),
            Item("Open log folder", lambda: a(app.open_log_folder)),
            Menu.SEPARATOR,
            Item("Quit FaceLock", lambda: a(app.quit)),
        )
        self.icon = pystray.Icon(APP_NAME, self._image("blue"), APP_NAME, menu)

    def _image(self, color):
        if color not in self._icons:
            self._icons[color] = make_icon(color)
        return self._icons[color]

    def start(self):
        self.icon.run_detached()

    def update(self, state, text):
        if state is not self.state:
            self.state = state
            self.icon.icon = self._image(STATE_COLOR.get(state, "blue"))
        if text != self.status_text:
            self.status_text = text
            self.icon.title = f"{APP_NAME}: {text}"[:127]
            self.icon.update_menu()

    def notify(self, message):
        try:
            self.icon.notify(message, APP_NAME)
        except Exception:
            pass

    def stop(self):
        self.icon.stop()
