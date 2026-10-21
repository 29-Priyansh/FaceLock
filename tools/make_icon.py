"""Writes assets/facelock.ico for the exe."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from facelock.ui.icons import make_icon  # noqa: E402

os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
out = os.path.join(ROOT, "assets", "facelock.ico")
make_icon("blue", 256).save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote", out)
