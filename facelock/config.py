"""Settings with defaults, persisted as JSON in %LOCALAPPDATA%\\FaceLock."""
import json
import logging
import os
import sys

from . import APP_NAME

log = logging.getLogger(__name__)

DEFAULTS = {
    "lock_after_s": 10,                 # countdown length once you are not seen
    "sample_interval_s": 3.0,           # time between camera grabs while you are present
    "countdown_sample_interval_s": 0.3, # sampling while the countdown runs (camera stays open)
    "match_threshold": 0.363,           # SFace cosine similarity; OpenCV's published default
    "camera_index": 0,
    "dev_mode": True,                   # shows Cancel on the countdown
    "cancel_pause_min": 5,              # Cancel pauses monitoring this long
    "busy_retry_s": 5.0,                # how often to re-check a camera that another app is using
}


def data_dir():
    path = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def resource_dir():
    """Folder holding bundled read-only resources (models, assets)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def models_dir():
    return os.path.join(resource_dir(), "models")


class Config(dict):
    def __init__(self, path=None):
        super().__init__(DEFAULTS)
        self.path = path or os.path.join(data_dir(), "config.json")
        self.load()

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                stored = json.load(f)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as e:
            log.warning("config unreadable, using defaults: %s", e)
            return
        for key, default in DEFAULTS.items():
            if key in stored:
                try:
                    self[key] = type(default)(stored[key])
                except (TypeError, ValueError):
                    log.warning("bad config value %s=%r ignored", key, stored[key])

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dict(self), f, indent=2)
        os.replace(tmp, self.path)
