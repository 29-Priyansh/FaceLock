"""Live preview with boxes, similarity scores, timings and process CPU/RAM.
The camera is used only while this window is open."""
import os
import time
import tkinter as tk

from .. import winapi
from ..profile_store import ProfileError
from ..vision import FaceEngine
from .preview import CaptureThread, draw_face, to_photo


class DiagnosticsWindow:
    def __init__(self, root, cfg, store, monitor, on_close=None):
        self.cfg, self.monitor, self.on_close = cfg, monitor, on_close
        try:
            self.gallery = store.load()
        except ProfileError:
            self.gallery = None
        win = self.win = tk.Toplevel(root)
        win.title("FaceLock - Diagnostics")
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self.close)
        self.video = tk.Label(win, bg="black", width=480, height=360)
        self.video.pack(padx=10, pady=10)
        self.info = tk.Label(win, text="Starting camera...", font=("Consolas", 10), justify="left", anchor="w")
        self.info.pack(fill="x", padx=10, pady=(0, 10))
        self.done = False
        self._photo = None
        self._cpu = (time.perf_counter(), time.process_time())
        self._cpu_pct = 0.0

        self.monitor.post("ui_camera", True)
        self.engine = FaceEngine()
        self.thread = CaptureThread(cfg["camera_index"], self._process)
        self.thread.start()
        win.after(50, self._tick)

    def _process(self, frame):
        t0 = time.perf_counter()
        best, faces, scores = self.engine.match(frame, self.gallery)
        ms = (time.perf_counter() - t0) * 1000
        thr = self.cfg["match_threshold"]
        view = frame.copy()
        for i, f in enumerate(faces):
            s = scores[i] if i < len(scores) else None
            me = s is not None and s >= thr
            label = "no profile" if s is None else f"{'YOU' if me else 'not you'} {s:.2f}"
            draw_face(view, f, (0, 200, 0) if me else (0, 0, 255), label)
        return view, best, len(faces), ms, float(frame.mean())

    def _tick(self):
        if self.done:
            return
        result = self.thread.latest()
        if result is not None:
            view, best, n, ms, brightness = result
            self._photo = to_photo(view)
            self.video.config(image=self._photo, width=0, height=0)
            now = (time.perf_counter(), time.process_time())
            if now[0] - self._cpu[0] >= 1.0:
                self._cpu_pct = (now[1] - self._cpu[1]) / (now[0] - self._cpu[0]) / os.cpu_count() * 100
                self._cpu = now
            thr = self.cfg["match_threshold"]
            verdict = "YOU -> stays unlocked" if best >= thr else "you are not recognised -> countdown"
            self.info.config(text=(
                f"faces: {n}   best similarity: {best:.3f}   threshold: {thr:.3f}   => {verdict}\n"
                f"detect+match: {ms:.1f} ms   frame brightness: {brightness:.0f}\n"
                f"process CPU: {self._cpu_pct:.1f}% (preview runs continuously)   "
                f"RAM: {winapi.working_set_mb():.0f} MB"))
        if self.thread.error:
            self.info.config(text=self.thread.error)
            return
        self.win.after(40, self._tick)

    def close(self):
        self.done = True
        self.thread.stop()
        self.thread.join(2)
        self.monitor.post("ui_camera", False)
        self.win.destroy()
        if self.on_close:
            self.on_close()
