"""Live camera capture for the Enroll and Diagnostics windows.

The capture runs on its own thread; the Tk window polls `latest()` with `after()`.
The monitor is told to release the camera first (Monitor.post("ui_camera", True)).
"""
import queue
import threading
import time
import tkinter as tk

import cv2

from ..camera import Camera


class CaptureThread(threading.Thread):
    def __init__(self, camera_index, process):
        """process(frame) -> result; runs on this thread for every frame."""
        super().__init__(name="Preview", daemon=True)
        self.camera = Camera(camera_index)
        self.process = process
        self.results = queue.Queue(maxsize=1)
        self.error = None
        self._halt = threading.Event()

    def run(self):
        deadline = time.time() + 6  # the monitor may still be finishing a sample
        while not self._halt.is_set() and not self.camera.open():
            if time.time() > deadline:
                self.error = "Could not open the camera (is another app using it?)"
                return
            time.sleep(0.3)
        try:
            while not self._halt.is_set():
                frame = self.camera.read()
                if frame is None:
                    self.error = "Camera stopped delivering frames"
                    return
                result = self.process(frame)
                try:
                    self.results.get_nowait()
                except queue.Empty:
                    pass
                self.results.put(result)
        finally:
            self.camera.release()

    def latest(self):
        try:
            return self.results.get_nowait()
        except queue.Empty:
            return None

    def stop(self):
        self._halt.set()


def to_photo(bgr, width=480):
    h, w = bgr.shape[:2]
    img = cv2.resize(bgr, (width, round(h * width / w)))
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    header = b"P6 %d %d 255 " % (rgb.shape[1], rgb.shape[0])
    return tk.PhotoImage(data=header + rgb.tobytes(), format="PPM")


def draw_face(frame, face, color, label=None):
    x, y, w, h = (int(v) for v in face[:4])
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
    if label:
        cv2.putText(frame, label, (x, max(18, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
