import numpy as np
import pytest

from facelock.profile_store import ProfileError, ProfileStore


def test_roundtrip(tmp_path):
    store = ProfileStore(str(tmp_path / "p.bin"))
    assert store.load() is None
    emb = np.random.rand(20, 128).astype(np.float32)
    store.save(emb)
    raw = (tmp_path / "p.bin").read_bytes()
    assert emb.tobytes() not in raw  # encrypted at rest
    np.testing.assert_array_equal(store.load(), emb)


def test_tamper_rejected(tmp_path):
    store = ProfileStore(str(tmp_path / "p.bin"))
    store.save(np.ones((3, 128), np.float32))
    raw = bytearray((tmp_path / "p.bin").read_bytes())
    raw[len(raw) // 2] ^= 0xFF
    (tmp_path / "p.bin").write_bytes(bytes(raw))
    with pytest.raises(ProfileError):
        store.load()


def test_replaced_file_rejected(tmp_path):
    (tmp_path / "p.bin").write_bytes(b'{"model": "x"}')
    with pytest.raises(ProfileError):
        ProfileStore(str(tmp_path / "p.bin")).load()


def test_delete(tmp_path):
    store = ProfileStore(str(tmp_path / "p.bin"))
    store.save(np.ones((1, 128), np.float32))
    store.delete()
    assert store.load() is None
    store.delete()  # idempotent
