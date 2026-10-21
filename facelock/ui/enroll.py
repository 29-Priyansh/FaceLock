"""Face scanning windows.

Enroll (start over): five head poses x four samples -> replaces the profile.
Improve: a longer timed session that sweeps your head through every angle you use
(turning left/right, keyboard, side monitors, leaning back, moving naturally) and ADDS
samples. It detects faces exactly like the monitor does, so every angle captured here
is an angle the monitor recognises afterwards. The live box shows green when the
current angle is already recognised and amber while it is being learned.
Run it as often as you like - in other lighting, with/without glasses - each run only
keeps what is new:
  - a sample must still look like you (similar to your profile or to samples taken
    earlier in this session, while you are the only face in view), and
  - near-duplicates of what the profile already knows are skipped.
Only embeddings are stored, never images.
"""
import time
import tkinter as tk
from tkinter import ttk

import numpy as np

from ..vision import FaceEngine, quality
from .preview import CaptureThread, draw_face, to_photo

ENROLL_STEPS = [
    ("Look straight at the camera", None),
    ("Turn your head slightly LEFT", None),
    ("Turn your head slightly RIGHT", None),
    ("Tilt your head slightly UP", None),
    ("Tilt your head slightly DOWN", None),
]
ENROLL_PER_STEP = 4

IMPROVE_STEPS = [  # (instruction, seconds) - turn SLOWLY so each new angle links to the last
    ("Look straight at the screen", 5),
    ("SLOWLY turn your head all the way LEFT, then back", 8),
    ("SLOWLY turn your head all the way RIGHT, then back", 8),
    ("Look down at your keyboard / phone", 6),
    ("Look up, then lean back in your chair", 6),
    ("Look at the far LEFT edge / left monitor", 6),
    ("Look at the far RIGHT edge / right monitor", 6),
    ("Rest your chin on your hand, drink something", 6),
    ("Move naturally: talk, laugh, shift in your seat", 20),
]

MIN_GAP_S = 0.3
MAX_SAMPLES = 400        # profile cap; the most redundant samples are dropped beyond this
VERIFY_MIN = 0.30        # improve: a new sample must be at least this similar to you
NOVELTY_MAX = 0.93       # improve: more similar than this to an existing sample = already known


def prune(gallery, cap=MAX_SAMPLES):
    """Drop the most redundant samples until the gallery fits the cap."""
    g = np.asarray(gallery, np.float32)
    if len(g) <= cap:
        return g
    sim = g @ g.T
    np.fill_diagonal(sim, -1)
    keep = np.ones(len(g), bool)
    for _ in range(len(g) - cap):
        s = np.where(keep[:, None] & keep[None, :], sim, -1).max(axis=1)
        s[~keep] = -2
        keep[int(np.argmax(s))] = False
    return g[keep]


class EnrollWindow:
    def __init__(self, root, cfg, store, monitor, improve=False, on_close=None):
        self.cfg, self.store, self.monitor, self.improve = cfg, store, monitor, improve
        self.on_close = on_close
        self.steps = IMPROVE_STEPS if improve else ENROLL_STEPS
        self.existing = None
        if improve:
            try:
                self.existing = store.load()
            except Exception:
                self.existing = None
        self._refs = self.existing  # what the profile knows so far (read by the capture thread)
        self.capturing = False
        self.done = False
        self.last_capture = 0.0
        self._reset_counters()

        win = self.win = tk.Toplevel(root)
        win.title("FaceLock - " + ("Improve face recognition" if improve else "Enroll your face"))
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self.close)
        self.video = tk.Label(win, bg="black", width=480, height=360)
        self.video.pack(padx=10, pady=(10, 4))
        intro = ("Sit as you normally do. You will be asked to look at different places\n"
                 "for about 70 s. Repeat later in other lighting or with/without glasses."
                 if improve else "Sit as you normally do, then press Start.")
        self.instruction = tk.Label(win, text=intro, font=("Segoe UI", 12, "bold"))
        self.instruction.pack(pady=(4, 0))
        self.hint = tk.Label(win, text="", font=("Segoe UI", 9), fg="#555")
        self.hint.pack()
        total = sum(s for _, s in self.steps) if improve else len(self.steps) * ENROLL_PER_STEP
        self.progress = ttk.Progressbar(win, length=480, maximum=total)
        self.progress.pack(padx=10, pady=6)
        self.counts = tk.Label(win, text=self._profile_text(), font=("Segoe UI", 9))
        self.counts.pack()
        bar = tk.Frame(win)
        bar.pack(pady=(4, 10))
        self.start_btn = tk.Button(bar, text="Start", width=12, command=self.start)
        self.start_btn.pack(side="left", padx=4)
        tk.Button(bar, text="Close", width=12, command=self.close).pack(side="left", padx=4)
        tk.Label(win, text="Only numeric face features are saved (encrypted for your Windows account). "
                           "No photos are stored.", font=("Segoe UI", 8), fg="#777").pack(pady=(0, 8))

        self.monitor.post("ui_camera", True)
        self.engine = FaceEngine()
        self.thread = CaptureThread(cfg["camera_index"], self._process)
        self.thread.start()
        self._photo = None
        win.after(50, self._tick)

    def _accept(self, emb):
        self.samples.append(emb)
        known = self.existing if self.existing is not None else np.zeros((0, 128), np.float32)
        self._refs = np.concatenate([known, np.stack(self.samples)])

    def _reset_counters(self):
        self._refs = getattr(self, "existing", None)
        self.samples = []
        self.step = 0
        self.step_started = 0.0
        self.known = 0
        self.rejected = 0

    def _profile_text(self):
        n = 0 if self.existing is None else len(self.existing)
        if not self.improve:
            return ""
        return (f"Profile: {n} samples   |   this session: {len(self.samples)} new, "
                f"{self.known} already known, {self.rejected} not matching")

    # -- capture thread -------------------------------------------------------

    def _process(self, frame):
        faces = self.engine.detect(frame)
        view = frame.copy()
        if len(faces) != 1:
            msg = "No face found" if len(faces) == 0 else "Only you should be in view"
            for f in faces:
                draw_face(view, f, (0, 0, 255))
            return view, False, msg, None
        face = faces[0]
        # Improve accepts every face the monitor would detect: turned heads are the point.
        ok, msg = quality(frame, face, strict=not self.improve)
        emb = self.engine.embed(frame, face) if ok else None
        refs = self._refs
        if emb is not None and refs is not None and len(refs):
            score = float(np.max(refs @ emb))
            known = score >= self.cfg["match_threshold"]
            draw_face(view, face, (0, 200, 0) if known else (0, 170, 255),
                      f"{'recognised' if known else 'learning'} {score:.2f}")
        else:
            draw_face(view, face, (0, 200, 0) if ok else (0, 170, 255))
        capture = None
        if emb is not None and self.capturing and time.time() - self.last_capture >= MIN_GAP_S:
            capture = emb
            self.last_capture = time.time()
        return view, ok, msg, capture

    # -- Tk thread ------------------------------------------------------------

    def _tick(self):
        if self.done:
            return
        result = self.thread.latest()
        if result is not None:
            view, ok, msg, emb = result
            self._photo = to_photo(view)
            self.video.config(image=self._photo, width=0, height=0)
            if self.capturing:
                self.hint.config(text="Hold / move slowly..." if ok else msg)
            else:
                self.hint.config(text="Face OK" if ok else msg)
            if emb is not None:
                self._add_sample(emb)
        if self.capturing and self.improve:
            self._advance_timed()
        if self.thread.error:
            self.instruction.config(text=self.thread.error)
            self.start_btn.config(state="disabled")
            return
        self.win.after(40, self._tick)

    def start(self):
        self._reset_counters()
        self.progress["value"] = 0
        self.capturing = True
        self.step_started = time.time()
        self.start_btn.config(state="disabled")
        self.instruction.config(text=self.steps[0][0])
        self.counts.config(text=self._profile_text())

    def _advance_timed(self):
        elapsed_before = sum(s for _, s in self.steps[:self.step])
        in_step = time.time() - self.step_started
        self.progress["value"] = elapsed_before + min(in_step, self.steps[self.step][1])
        if in_step >= self.steps[self.step][1]:
            self.step += 1
            if self.step >= len(self.steps):
                self._finish()
                return
            self.step_started = time.time()
            self.instruction.config(text=self.steps[self.step][0])
            self.last_capture = time.time() + 0.6  # time to change pose

    def _add_sample(self, emb):
        if self.improve:
            refs = self._refs
            if refs is not None and len(refs):
                best = float(np.max(refs @ emb))
                if best < VERIFY_MIN:
                    self.rejected += 1
                    self.counts.config(text=self._profile_text())
                    return
                if best > NOVELTY_MAX:
                    self.known += 1
                    self.counts.config(text=self._profile_text())
                    return
            self._accept(emb)
            self.counts.config(text=self._profile_text())
            return
        self._accept(emb)
        self.progress["value"] = len(self.samples)
        if len(self.samples) % ENROLL_PER_STEP == 0:
            self.step += 1
            if self.step >= len(self.steps):
                self._finish()
            else:
                self.instruction.config(text=self.steps[self.step][0])
                self.last_capture = time.time() + 0.8

    def _finish(self):
        self.capturing = False
        thr = self.cfg["match_threshold"]
        if not self.samples:
            self.instruction.config(text="Nothing new learned - your profile already covers these poses.")
            self.hint.config(text="Try again in different lighting, with/without glasses, or another seat.")
            self.start_btn.config(text="Run again", state="normal")
            return
        new = np.stack(self.samples)
        base = self.existing if self.improve else None   # Enroll (and its Redo) replaces
        gallery = new if base is None else np.concatenate([base, new])
        gallery = prune(gallery)
        self.store.save(gallery)
        self.existing = gallery
        # Leave-one-out self-match on the saved profile: how well each sample matches the rest.
        sim = gallery @ gallery.T
        np.fill_diagonal(sim, -1)
        loo = sim.max(axis=1)
        weak = int((loo < thr).sum())
        added = f"Added {len(new)} new samples. " if self.improve else ""
        self.instruction.config(text=f"{added}Profile now has {len(gallery)} samples.")
        self.hint.config(text=f"Self-match min {loo.min():.2f} / mean {loo.mean():.2f} (threshold {thr:.2f})"
                              + (f", {weak} isolated pose(s)" if weak else "")
                              + (". Run Improve again to keep refining." if self.improve
                                 else ". Next: tray > Improve face recognition."))
        self.counts.config(text=self._profile_text())
        self.monitor.post("reload_profile")
        self.start_btn.config(text="Run again" if self.improve else "Redo", state="normal")

    def close(self):
        self.done = True
        self.thread.stop()
        self.thread.join(2)
        self.monitor.post("ui_camera", False)
        self.win.destroy()
        if self.on_close:
            self.on_close()
