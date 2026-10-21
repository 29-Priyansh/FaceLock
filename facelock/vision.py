"""Face detection (YuNet) and recognition (SFace) via OpenCV's built-in wrappers.

Detection runs on the full 640x480 frame with a permissive confidence cut-off so that
turned, tilted and partly hidden faces are still found; whether a face is YOU is
decided only by recognition against your enrolled samples. Monitoring and the
Improve scan use the same settings, so every angle you scan is an angle that is found.

Measured on this laptop (i7-10850H, CPU, 1 thread): detect at 640 px ~23 ms,
align + embed ~13 ms per face.
"""
import os

import cv2
import numpy as np

from .config import models_dir

# Measured: OpenCV's thread pool burns 2-3x more CPU time for the same wall time on
# these small models.
cv2.setNumThreads(1)

DETECTOR = "face_detection_yunet_2023mar.onnx"
RECOGNIZER = "face_recognition_sface_2021dec.onnx"
DETECT_WIDTH = 640
DETECT_SCORE = 0.5      # YuNet confidence; low on purpose (turned faces score lower)
MIN_FACE_PX = 40


class FaceEngine:
    def __init__(self, model_dir=None, score_threshold=DETECT_SCORE):
        d = model_dir or models_dir()
        self.detector = cv2.FaceDetectorYN.create(os.path.join(d, DETECTOR), "", (DETECT_WIDTH, 480),
                                                  score_threshold, 0.3, 50)
        self.recognizer = cv2.FaceRecognizerSF.create(os.path.join(d, RECOGNIZER), "")

    def detect(self, frame):
        """Faces as an (N, 15) float32 array in full-frame coordinates, largest first."""
        h, w = frame.shape[:2]
        scale = min(1.0, DETECT_WIDTH / w)
        small = cv2.resize(frame, (round(w * scale), round(h * scale))) if scale < 1 else frame
        self.detector.setInputSize((small.shape[1], small.shape[0]))
        _, faces = self.detector.detect(small)
        if faces is None:
            return np.zeros((0, 15), np.float32)
        faces = faces.copy()
        faces[:, :14] /= scale
        faces = faces[(faces[:, 2] >= MIN_FACE_PX) & (faces[:, 3] >= MIN_FACE_PX)]
        return faces[np.argsort(-(faces[:, 2] * faces[:, 3]))]

    def embed(self, frame, face):
        """L2-normalised 128-d embedding."""
        crop = self.recognizer.alignCrop(frame, face)
        feat = self.recognizer.feature(crop).flatten().astype(np.float32)
        return feat / (np.linalg.norm(feat) + 1e-9)

    def match(self, frame, gallery):
        """Compare every face in the frame with the enrolled gallery (K, 128).

        Returns (best_score, faces, per_face_scores). best_score is -1 when no face."""
        faces = self.detect(frame)
        if len(faces) == 0 or gallery is None or len(gallery) == 0:
            return -1.0, faces, []
        scores = [float(np.max(gallery @ self.embed(frame, f))) for f in faces]
        return max(scores), faces, scores


def quality(frame, face, strict=True):
    """Scan quality checks. Returns (ok, reason).

    strict (first enrollment): clear, well-lit, fairly large faces only.
    relaxed (Improve): anything the monitor itself would detect and that is not too
    dark or blurred to describe - turned and tilted faces are exactly what it is for."""
    x, y, w, h = face[:4]
    min_size = 64 if strict else MIN_FACE_PX
    if w < min_size or h < min_size:
        return False, "Move closer to the camera"
    fh, fw = frame.shape[:2]
    if strict and (x < 0 or y < 0 or x + w > fw or y + h > fh):
        return False, "Keep your whole face in view"
    x0, y0 = max(0, int(x)), max(0, int(y))
    roi = cv2.cvtColor(frame[y0:int(y + h), x0:int(x + w)], cv2.COLOR_BGR2GRAY)
    if roi.size == 0:
        return False, "Keep your face in view"
    brightness = float(roi.mean())
    if brightness < (50 if strict else 35):
        return False, "Too dark - add some light"
    if brightness > 220:
        return False, "Too bright"
    if cv2.Laplacian(roi, cv2.CV_64F).var() < (30 if strict else 12):
        return False, "Hold still (blurry)"
    if strict and face[14] < 0.85:
        return False, "Face not clear enough"
    return True, "OK"
