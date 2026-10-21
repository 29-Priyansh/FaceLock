"""Background worker: camera -> face match -> presence state -> lock."""
import logging
import queue
import threading
import time

from . import winapi
from .camera import Camera
from .presence import LOCK, Presence, State
from .profile_store import ProfileError, ProfileStore
from .vision import FaceEngine

log = logging.getLogger(__name__)

SESSION_POLL_S = 2.0  # safety net in case a session notification is missed


class Monitor(threading.Thread):
    def __init__(self, cfg, store: ProfileStore, on_status, on_notify):
        super().__init__(name="Monitor", daemon=True)
        self.cfg = cfg
        self.store = store
        self.on_status = on_status      # called with a status dict (from this thread)
        self.on_notify = on_notify      # called with a short user-facing message
        self.presence = Presence(cfg["lock_after_s"])
        self.camera = Camera(cfg["camera_index"])
        self.engine = None
        self.gallery = None
        self.ui_owns_camera = False
        self.busy_apps = []
        self._cmds = queue.Queue()
        self._wake = threading.Event()
        self._stopping = False
        self._last_session_poll = 0.0

    # -- called from other threads -------------------------------------------

    def post(self, cmd, arg=None):
        self._cmds.put((cmd, arg))
        self._wake.set()

    def stop(self):
        self._stopping = True
        self._wake.set()

    # -- worker ---------------------------------------------------------------

    def run(self):
        while not self._stopping:
            try:
                self._loop()
            except Exception:
                log.exception("monitor crashed; restarting in 5 s")
                self.camera.release()
                self.on_notify("Monitoring hit an error and is restarting.")
                self._sleep(5)
        self.camera.release()
        log.info("monitor stopped")

    def _sleep(self, seconds):
        self._wake.wait(max(0.0, seconds))
        self._wake.clear()

    def _load_profile(self):
        try:
            self.gallery = self.store.load()
        except ProfileError as e:
            log.error("%s", e)
            self.gallery = None
            self.on_notify("Face profile is unreadable - please enroll again.")
        self.presence.set_enrolled(self.gallery is not None)
        log.info("profile loaded: %s samples", 0 if self.gallery is None else len(self.gallery))

    def _handle(self, cmd, arg):
        now = time.monotonic()
        p = self.presence
        if cmd == "session":
            if arg in ("lock", "unlock"):
                p.set_session_locked(arg == "lock")
            elif arg in ("display_off", "display_on"):
                p.set_display_off(arg == "display_off")
                if arg == "display_on":
                    p.set_suspended(False)
            elif arg in ("suspend", "resume"):
                p.set_suspended(arg == "suspend")
            if arg in ("lock", "display_off", "suspend"):
                self.camera.release()
            log.info("session event: %s", arg)
        elif cmd == "pause":
            p.pause(now, arg)
        elif cmd == "resume":
            p.resume()
        elif cmd == "reload_profile":
            self._load_profile()
        elif cmd == "reload_config":
            p.lock_after_s = self.cfg["lock_after_s"]
            if self.camera.index != self.cfg["camera_index"]:
                self.camera.release()
                self.camera = Camera(self.cfg["camera_index"])
        elif cmd == "ui_camera":
            self.ui_owns_camera = bool(arg)
            self.camera.release()

    def _poll_session(self, now):
        if now - self._last_session_poll >= SESSION_POLL_S:
            self._last_session_poll = now
            locked = winapi.is_session_locked()
            if locked is not None:
                self.presence.set_session_locked(locked)

    def _publish(self, now, detail=""):
        p = self.presence
        state = p.state(now)
        if self.ui_owns_camera and state not in (State.NOT_ENROLLED, State.LOCKED, State.SUSPENDED):
            state, detail = State.PAUSED, "FaceLock window is using the camera"
        if state is State.CAMERA_BUSY and self.busy_apps:
            detail = ", ".join(a.split("#")[-1] for a in self.busy_apps)
        self.on_status({
            "state": state,
            "remaining": p.remaining(now),
            "score": p.last_score,
            "paused_for": None if p.paused_until <= now else p.paused_until - now,
            "detail": detail,
        })

    def _check_busy(self):
        """True if another app is using the camera (we must stay away)."""
        others = self.camera.other_apps()
        if not others:
            self.busy_apps = []
            return False
        self.camera.release()
        self.busy_apps = others
        return True

    def _sample(self, keep_open):
        """(best similarity score, face count) from 1-2 frames, or None if the camera gave nothing."""
        if not self.camera.open():
            return None
        try:
            best, count = None, 0
            for _ in range(1 if keep_open else 2):
                frame = self.camera.read()
                if frame is None:
                    continue
                score, faces, _ = self.engine.match(frame, self.gallery)
                count = max(count, len(faces))
                best = score if best is None else max(best, score)
                if best >= self.cfg["match_threshold"]:
                    break
            return None if best is None else (best, count)
        finally:
            if not keep_open:
                self.camera.release()

    def _loop(self):
        if self.engine is None:
            self.engine = FaceEngine()
        self._load_profile()
        camera_failures = 0
        while not self._stopping:
            while True:
                try:
                    self._handle(*self._cmds.get_nowait())
                except queue.Empty:
                    break
            now = time.monotonic()
            self._poll_session(now)
            p = self.presence

            if self.ui_owns_camera or (not p.monitoring(now) and p.state(now) is not State.CAMERA_BUSY):
                self.camera.release()
                self._publish(now)
                self._sleep(1.0)
                continue

            if self._check_busy():
                if not p.camera_busy:
                    log.info("camera in use by %s - stepping aside", self.busy_apps)
                p.set_camera_busy(True)
                self._publish(now)
                self._sleep(self.cfg["busy_retry_s"])
                continue

            state = p.state(now)
            if state is State.CAMERA_BUSY and camera_failures == 0:
                p.set_camera_busy(False)
                log.info("camera free again - resuming")
                state = p.state(now)
            if not p.monitoring(now) and state is not State.CAMERA_BUSY:
                self._sleep(0.2)
                continue

            result = self._sample(keep_open=p.urgent())
            now = time.monotonic()
            if result is None:
                camera_failures += 1
                if camera_failures == 1:
                    log.warning("camera unavailable (open/read failed)")
                p.set_camera_busy(True)
                self.camera.release()
                self._publish(now, "Camera unavailable")
                self._sleep(self.cfg["busy_retry_s"])
                continue
            if camera_failures:
                camera_failures = 0
                p.set_camera_busy(False)

            score, faces = result
            action = p.update(now, seen=score >= self.cfg["match_threshold"], score=score)
            log.debug("sample faces=%d score=%.2f -> %s", faces, score, p.state(now).name)
            if action == LOCK:
                self.camera.release()
                log.info("locking workstation (last score %.3f, faces %d)", score, faces)
                winapi.lock_workstation()
            self._publish(now)

            if p.urgent():
                self._sleep(self.cfg["countdown_sample_interval_s"])
                continue
            self.camera.release()
            if p.state(now) is State.PRESENT:
                self._sleep(self.cfg["sample_interval_s"])
            else:
                self._sleep(0.5)
