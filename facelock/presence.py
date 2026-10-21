"""Presence state machine. Pure logic: no camera, no Win32, time is passed in.

Rule: your face recognised (at any angle your profile covers; other people in view are
ignored) -> present. Not recognised -> one quick confirmation sample, then the
countdown; at zero the caller locks the workstation. Side states (not enrolled, locked,
display off / suspended, paused, camera in use by another app) never lock.
"""
import enum
import math


class State(enum.Enum):
    NOT_ENROLLED = "Not enrolled"
    LOCKED = "Locked"
    SUSPENDED = "Screen off"
    PAUSED = "Paused"
    CAMERA_BUSY = "Camera in use by another app"
    STARTING = "Starting"
    PRESENT = "You are here"
    COUNTDOWN = "Locking soon"


LOCK = "lock"
LOCK_RETRY_S = 5.0  # if no session-lock notification arrives after a lock request, allow another


class Presence:
    def __init__(self, lock_after_s=10.0):
        self.lock_after_s = lock_after_s
        self.enrolled = False
        self.session_locked = False
        self.display_off = False
        self.suspended = False
        self.paused_until = 0.0          # monotonic time; math.inf = until resumed
        self.camera_busy = False
        self.countdown_start = None
        self.suspect_since = None        # first miss, waiting for a confirmation sample
        self.seen_once = False
        self.lock_requested_at = None
        self.last_score = None

    # -- inputs ---------------------------------------------------------------

    def _reset_countdown(self):
        self.countdown_start = None
        self.suspect_since = None

    def set_enrolled(self, value):
        self.enrolled = value
        self._reset_countdown()

    def set_session_locked(self, value):
        if value != self.session_locked:
            self.session_locked = value
            self._reset_countdown()
            self.lock_requested_at = None
            if not value:
                self.seen_once = False  # after unlock, wait for a fresh sample

    def set_display_off(self, value):
        self.display_off = value
        self._reset_countdown()

    def set_suspended(self, value):
        self.suspended = value
        self._reset_countdown()

    def pause(self, now, seconds):
        self.paused_until = math.inf if seconds is None else now + seconds
        self._reset_countdown()

    def resume(self):
        self.paused_until = 0.0
        self._reset_countdown()

    def set_camera_busy(self, value):
        if value != self.camera_busy:
            self.camera_busy = value
            self._reset_countdown()

    def lock_requested(self, now):
        self.lock_requested_at = now
        self._reset_countdown()

    # -- state ----------------------------------------------------------------

    def state(self, now):
        if not self.enrolled:
            return State.NOT_ENROLLED
        if self.session_locked or (self.lock_requested_at is not None
                                   and now - self.lock_requested_at < LOCK_RETRY_S):
            return State.LOCKED
        if self.display_off or self.suspended:
            return State.SUSPENDED
        if now < self.paused_until:
            return State.PAUSED
        if self.camera_busy:
            return State.CAMERA_BUSY
        if self.countdown_start is not None:
            return State.COUNTDOWN
        return State.PRESENT if self.seen_once else State.STARTING

    def monitoring(self, now):
        """True when the camera should be sampled."""
        return self.state(now) in (State.STARTING, State.PRESENT, State.COUNTDOWN)

    def urgent(self):
        """True while a miss is being confirmed or the countdown runs: sample fast."""
        return self.suspect_since is not None or self.countdown_start is not None

    def remaining(self, now):
        if self.countdown_start is None:
            return None
        return max(0.0, self.lock_after_s - (now - self.countdown_start))

    def update(self, now, seen=None, score=None):
        """Feed a sample (seen=True/False) or just a clock tick (seen=None).

        Returns LOCK when the workstation should be locked now, else None."""
        if not self.monitoring(now):
            return None
        if self.lock_requested_at is not None:
            self.lock_requested_at = None  # previous request did not lock the session; allow retry
        if score is not None:
            self.last_score = score
        if seen is True:
            self.seen_once = True
            self._reset_countdown()
        elif seen is False and self.countdown_start is None:
            if self.suspect_since is None:
                self.suspect_since = now     # could be a blink of the detector: re-check first
            else:
                self.suspect_since = None
                self.countdown_start = now
        if self.countdown_start is not None and now - self.countdown_start >= self.lock_after_s:
            self.lock_requested(now)
            return LOCK
        return None
