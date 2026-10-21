"""Camera access that stays out of the way of other apps.

Measured on this laptop (M0, tools/camera_probe.py):
- The webcam cannot be streamed by two apps at once: while one holds it, a second
  MSMF reader gets no frames. So FaceLock never keeps the camera open while you are
  present; it opens it, grabs a frame and releases it (duty cycle).
- DirectShow opens in ~0.2 s (MSMF ~2 s) and the first frame is already exposed.
- Windows records live camera use per app under ConsentStore\\webcam with
  LastUsedTimeStop == 0. Checking it costs < 1 ms, so we check before every grab and
  leave the camera alone while any other app is using it.
"""
import logging
import os
import sys
import time
import winreg

import cv2

log = logging.getLogger(__name__)

CONSENT_ROOT = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam"


def _own_keys():
    paths = {sys.executable, getattr(sys, "_base_executable", sys.executable)}
    return {os.path.abspath(p).replace("\\", "#").lower() for p in paths if p}


STALE_PROBE_AFTER_S = 60  # an "in use" entry stuck this long gets one check for staleness


class CameraUsage:
    """Reports which other apps Windows says are using the camera right now."""

    def __init__(self):
        self._own = _own_keys()
        self._stale = set()        # (key, LastUsedTimeStart) entries confirmed stale
        self._first_seen = {}      # (key, LastUsedTimeStart) -> monotonic time first seen in use
        self._probed = set()

    def _walk(self, path, depth, found):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
        except OSError:
            return
        with key:
            try:
                start, _ = winreg.QueryValueEx(key, "LastUsedTimeStart")
                stop, _ = winreg.QueryValueEx(key, "LastUsedTimeStop")
                name = path.rsplit("\\", 1)[-1]
                if start and stop == 0 and name.lower() not in self._own and (name, start) not in self._stale:
                    found.append((name, start))
            except OSError:
                pass
            if depth:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(key, i)
                    except OSError:
                        break
                    self._walk(path + "\\" + sub, depth - 1, found)
                    i += 1

    def others(self):
        found = []
        self._walk(CONSENT_ROOT, 2, found)
        now = time.monotonic()
        for e in found:
            self._first_seen.setdefault(e, now)
        return found

    def needs_probe(self, entries):
        """Entries in use for a long time that were never checked (possible crash leftovers)."""
        now = time.monotonic()
        return [e for e in entries
                if e not in self._probed and now - self._first_seen.get(e, now) >= STALE_PROBE_AFTER_S]

    def mark_probed(self, entries, stale):
        self._probed.update(entries)
        if stale:
            self._stale.update(entries)


class Camera:
    def __init__(self, index=0):
        self.index = index
        self.cap = None
        self.usage = CameraUsage()

    @property
    def is_open(self):
        return self.cap is not None

    def other_apps(self):
        """Names of other apps currently using the camera (empty list = free).

        An entry is trusted immediately (we step aside at once). Only an entry stuck
        "in use" for STALE_PROBE_AFTER_S gets checked once, without disturbing its owner:
        an MSMF reader gets no frames while the camera is held elsewhere (measured), and
        the holder's stream is unaffected. If we do get a frame, the entry is a leftover
        from an app that crashed mid-stream and is ignored from then on."""
        entries = self.usage.others()
        probe = self.usage.needs_probe(entries)
        if probe:
            self.release()
            cap = cv2.VideoCapture(self.index, cv2.CAP_MSMF)
            try:
                stale = bool(cap.isOpened() and cap.read()[0])
            finally:
                cap.release()
            self.usage.mark_probed(probe, stale)
            if stale:
                log.warning("ignoring stale camera-in-use entries: %s", [n for n, _ in probe])
                entries = [e for e in entries if e not in probe]
        return [name for name, _ in entries]

    def open(self):
        if self.cap is not None:
            return True
        t0 = time.perf_counter()
        cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            log.info("camera %d failed to open", self.index)
            return False
        self.cap = cap
        log.debug("camera opened in %.2fs", time.perf_counter() - t0)
        return True

    def read(self):
        if self.cap is None:
            return None
        ok, frame = self.cap.read()
        return frame if ok and frame is not None else None

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            log.debug("camera released")

    def grab(self, frames=2):
        """Open, read up to `frames` frames, release. Returns the list of frames read."""
        if not self.open():
            return []
        try:
            out = []
            for _ in range(frames):
                f = self.read()
                if f is not None:
                    out.append(f)
            return out
        finally:
            self.release()
