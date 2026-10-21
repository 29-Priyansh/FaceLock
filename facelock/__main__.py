import logging
import sys

from . import __version__, winapi
from . import log as logsetup


def main():
    winapi.enable_dpi_awareness()
    if not winapi.acquire_single_instance():
        import tkinter.messagebox as mb
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        mb.showinfo("FaceLock", "FaceLock is already running. Look for the padlock icon in the system tray.")
        return 0
    path = logsetup.setup(debug="--debug" in sys.argv)
    logging.getLogger(__name__).info("FaceLock %s starting (log: %s)", __version__, path)
    from .app import App
    App().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
