"""Enrolled face embeddings, encrypted at rest with DPAPI (current-user scope).

Only embeddings are stored (128 floats per sample), never images. A file that fails
to decrypt or parse is treated as "no profile" - FaceLock never fails open.
"""
import base64
import json
import logging
import os

import numpy as np

from . import winapi
from .config import data_dir
from .vision import RECOGNIZER

log = logging.getLogger(__name__)

ENTROPY = b"FaceLock.profile.v1"


class ProfileError(Exception):
    pass


class ProfileStore:
    def __init__(self, path=None):
        self.path = path or os.path.join(data_dir(), "profile.bin")

    def exists(self):
        return os.path.exists(self.path)

    def save(self, embeddings):
        emb = np.asarray(embeddings, dtype=np.float32)
        payload = json.dumps({
            "version": 1,
            "model": RECOGNIZER,
            "shape": list(emb.shape),
            "embeddings": base64.b64encode(emb.tobytes()).decode("ascii"),
        }).encode("utf-8")
        blob = winapi.dpapi_protect(payload, ENTROPY)
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(blob)
        os.replace(tmp, self.path)

    def load(self):
        """Returns an (K, 128) float32 array, None if not enrolled, raises ProfileError if corrupt."""
        try:
            with open(self.path, "rb") as f:
                blob = f.read()
        except FileNotFoundError:
            return None
        try:
            data = json.loads(winapi.dpapi_unprotect(blob, ENTROPY))
            if data.get("model") != RECOGNIZER:
                raise ProfileError("profile was made with a different model; please re-enroll")
            emb = np.frombuffer(base64.b64decode(data["embeddings"]), dtype=np.float32)
            emb = emb.reshape(data["shape"])
            if emb.ndim != 2 or emb.shape[1] != 128 or len(emb) == 0:
                raise ProfileError("profile has an unexpected shape")
            return emb
        except ProfileError:
            raise
        except Exception as e:
            raise ProfileError(f"profile could not be decrypted or parsed: {e}") from e

    def delete(self):
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass
