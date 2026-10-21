"""Model loading and matching logic. No camera or face images needed (no biometrics in the repo).
Live accuracy is checked with the Diagnostics window instead."""
import numpy as np

from facelock.vision import FaceEngine


def test_no_face_in_blank_frame():
    eng = FaceEngine()
    frame = np.full((480, 640, 3), 128, np.uint8)
    faces = eng.detect(frame)
    assert faces.shape == (0, 15)
    score, faces, scores = eng.match(frame, np.ones((1, 128), np.float32))
    assert score == -1.0 and scores == []


def test_prune_drops_most_redundant():
    from facelock.ui.enroll import prune
    rng = np.random.default_rng(0)
    g = rng.standard_normal((10, 128)).astype(np.float32)
    g /= np.linalg.norm(g, axis=1, keepdims=True)
    dupes = np.repeat(g[:1], 5, axis=0)                 # 5 copies of sample 0
    out = prune(np.concatenate([g, dupes]), cap=10)
    assert len(out) == 10
    assert (np.abs(out @ g[0] - 1) < 1e-5).sum() == 1   # only one copy of sample 0 survives


def test_match_without_gallery_is_not_present():
    eng = FaceEngine()
    frame = np.zeros((480, 640, 3), np.uint8)
    assert eng.match(frame, None)[0] == -1.0
