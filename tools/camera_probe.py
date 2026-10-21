"""M0 camera probe: enumerate cameras, measure open latency, detect IR-like streams,
and time face detection/recognition on real frames.

Usage:  .venv\\Scripts\\python tools\\camera_probe.py [--hold SECONDS]
--hold keeps camera 0 streaming so you can test whether other apps can open it.
"""
import argparse
import os
import time

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "models")


def probe(index, backend, name):
    t0 = time.perf_counter()
    cap = cv2.VideoCapture(index, backend)
    opened = cap.isOpened()
    t_open = time.perf_counter() - t0
    if not opened:
        print(f"[{name} {index}] not opened ({t_open:.2f}s)")
        return None
    t1 = time.perf_counter()
    ok, frame = cap.read()
    t_first = time.perf_counter() - t1
    if not ok or frame is None:
        print(f"[{name} {index}] opened but no frame")
        cap.release()
        return None
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    # IR streams typically come through as identical B/G/R channels.
    b, g, r = cv2.split(frame.astype(np.int16))
    chan_diff = float(np.mean(np.abs(b - g)) + np.mean(np.abs(g - r)))
    t2 = time.perf_counter()
    cap.release()
    t_close = time.perf_counter() - t2
    print(f"[{name} {index}] {w}x{h} @ {fps:.0f}fps  open={t_open:.2f}s first_frame={t_first:.2f}s "
          f"close={t_close:.2f}s mean={frame.mean():.0f} chan_diff={chan_diff:.1f} "
          f"{'(IR-like/grey)' if chan_diff < 1.0 else '(colour)'}")
    return frame


def time_models(frame):
    det = cv2.FaceDetectorYN.create(os.path.join(MODELS, "face_detection_yunet_2023mar.onnx"), "", (320, 240))
    for model in ("face_recognition_sface_2021dec.onnx", "face_recognition_sface_2021dec_int8.onnx"):
        if not os.path.exists(os.path.join(MODELS, model)):
            continue
        rec = cv2.FaceRecognizerSF.create(os.path.join(MODELS, model), "")
        h, w = frame.shape[:2]
        scale = 320 / w
        small = cv2.resize(frame, (320, int(h * scale)))
        det.setInputSize((small.shape[1], small.shape[0]))
        n = 20
        t0 = time.perf_counter()
        for _ in range(n):
            _, faces = det.detect(small)
        t_det = (time.perf_counter() - t0) / n * 1000
        count = 0 if faces is None else len(faces)
        t_rec = float("nan")
        if count:
            face = faces[0].copy()
            face[:14] /= scale  # map box + landmarks back to full-res frame
            t0 = time.perf_counter()
            for _ in range(n):
                crop = rec.alignCrop(frame, face)
                rec.feature(crop)
            t_rec = (time.perf_counter() - t0) / n * 1000
        print(f"  {model}: faces={count} detect={t_det:.1f}ms align+embed={t_rec:.1f}ms")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=float, default=0)
    args = ap.parse_args()

    print("OpenCV", cv2.__version__)
    first = None
    for backend, name in ((cv2.CAP_MSMF, "MSMF"), (cv2.CAP_DSHOW, "DSHOW")):
        for i in range(4):
            f = probe(i, backend, name)
            if f is not None and first is None and backend == cv2.CAP_MSMF:
                first = f
    if first is not None:
        print("Model timings on MSMF camera frame:")
        time_models(first)

    if args.hold:
        cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
        print(f"Holding camera 0 for {args.hold:.0f}s - open another camera app now.")
        end = time.time() + args.hold
        fails = 0
        while time.time() < end:
            ok, _ = cap.read()
            fails += 0 if ok else 1
            time.sleep(0.1)
        cap.release()
        print(f"Released. read failures while holding: {fails}")


if __name__ == "__main__":
    main()
