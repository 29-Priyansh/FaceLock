from facelock.presence import LOCK, LOCK_RETRY_S, Presence, State


def make():
    p = Presence(lock_after_s=10)
    p.set_enrolled(True)
    return p


def absent_until_lock(p, t, step=0.3):
    """Feed 'not seen' samples from time t; return the time LOCK fired."""
    while True:
        if p.update(t, seen=False) == LOCK:
            return t
        t += step
        assert t < 1000


def test_not_enrolled_never_locks():
    p = Presence(lock_after_s=10)
    assert p.state(0) is State.NOT_ENROLLED
    for t in range(30):
        assert p.update(t, seen=False) is None


def test_single_miss_is_only_suspect_then_countdown_then_lock():
    p = make()
    p.update(0, seen=True)
    assert p.update(3, seen=False) is None
    assert p.state(3) is State.PRESENT and p.urgent()   # confirming, no countdown yet
    assert p.update(3.5, seen=False) is None
    assert p.state(3.5) is State.COUNTDOWN
    assert p.remaining(3.5) == 10
    assert p.update(13.4) is None                       # clock tick alone
    assert p.update(13.5) == LOCK
    assert p.state(13.5) is State.LOCKED


def test_detector_blink_does_not_start_countdown():
    p = make()
    p.update(0, seen=True)
    p.update(3, seen=False)
    p.update(3.3, seen=True)
    assert p.state(3.3) is State.PRESENT and not p.urgent()


def test_face_returns_during_countdown_cancels():
    p = make()
    p.update(0, seen=True)
    p.update(1, seen=False)
    p.update(1.3, seen=False)
    assert p.update(10, seen=True) is None
    assert p.state(10) is State.PRESENT
    t = absent_until_lock(p, 20)
    assert 10 <= t - 20 <= 10.6


def test_single_lock_request_per_absence():
    p = make()
    t = absent_until_lock(p, 0)
    p.set_session_locked(True)
    for i in range(1, 100):
        assert p.update(t + i, seen=False) is None
    assert p.state(t + 50) is State.LOCKED


def test_failed_lock_allows_retry_after_grace():
    p = make()
    t = absent_until_lock(p, 0)
    assert p.update(t + LOCK_RETRY_S - 0.1, seen=False) is None
    assert p.state(t + LOCK_RETRY_S) is State.STARTING
    t2 = absent_until_lock(p, t + LOCK_RETRY_S)
    assert t2 > t + LOCK_RETRY_S + 10


def test_unlock_resets_and_requires_new_sample():
    p = make()
    absent_until_lock(p, 0)
    p.set_session_locked(True)
    p.set_session_locked(False)
    assert p.state(200) is State.STARTING
    p.update(200, seen=True)
    assert p.state(200) is State.PRESENT


def test_side_states_never_lock_and_reset_countdown():
    p = make()
    p.update(0, seen=True)
    p.update(1, seen=False)
    p.update(1.3, seen=False)
    p.set_camera_busy(True)
    assert p.state(5) is State.CAMERA_BUSY
    assert p.update(20, seen=False) is None
    p.set_camera_busy(False)
    assert p.state(20) is not State.COUNTDOWN and not p.urgent()

    p.pause(30, 60)
    assert p.state(31) is State.PAUSED
    assert p.update(85, seen=False) is None
    assert p.state(90) is not State.PAUSED

    for setter in (p.set_display_off, p.set_suspended):
        setter(True)
        assert p.state(100) is State.SUSPENDED
        assert p.update(200, seen=False) is None
        setter(False)


def test_pause_until_resumed():
    p = make()
    p.pause(0, None)
    assert p.state(10 ** 9) is State.PAUSED
    p.resume()
    assert p.state(10 ** 9) is State.STARTING
