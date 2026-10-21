"""Tray / exe icons drawn with Pillow: a white padlock on a coloured disc."""
from PIL import Image, ImageDraw

from ..presence import State

COLORS = {
    "green": (34, 160, 90),
    "amber": (230, 150, 20),
    "grey": (120, 120, 120),
    "red": (200, 50, 50),
    "blue": (40, 110, 200),
}

STATE_COLOR = {
    State.PRESENT: "green",
    State.STARTING: "green",
    State.COUNTDOWN: "amber",
    State.PAUSED: "grey",
    State.LOCKED: "grey",
    State.SUSPENDED: "grey",
    State.CAMERA_BUSY: "red",
    State.NOT_ENROLLED: "red",
}


def make_icon(color="blue", size=64):
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((1, 1, s - 2, s - 2), fill=COLORS[color] + (255,))
    white = (255, 255, 255, 255)
    bw, bh = s * 0.44, s * 0.30
    bx, by = (s - bw) / 2, s * 0.46
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=s * 0.05, fill=white)
    sw = s * 0.07
    d.arc((bx + bw * 0.15, s * 0.22, bx + bw * 0.85, by + s * 0.12), 180, 360, fill=white, width=max(2, int(sw)))
    d.line((bx + bw * 0.15 + sw / 2, s * 0.37, bx + bw * 0.15 + sw / 2, by), fill=white, width=max(2, int(sw)))
    d.line((bx + bw * 0.85 - sw / 2, s * 0.37, bx + bw * 0.85 - sw / 2, by), fill=white, width=max(2, int(sw)))
    return img
