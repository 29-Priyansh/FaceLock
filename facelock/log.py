import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from .config import data_dir


def setup(debug=False):
    path = os.path.join(data_dir(), "facelock.log")
    handlers = [RotatingFileHandler(path, maxBytes=1_000_000, backupCount=1, encoding="utf-8")]
    if sys.stderr is not None and not getattr(sys, "frozen", False):
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s",
        handlers=handlers,
    )
    return path
