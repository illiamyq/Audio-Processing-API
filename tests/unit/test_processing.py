import numpy as np

from app.tasks.processing import _compute_snr, _ext


def test_snr_identical_signals():
    y = np.ones(1000) * 0.5
    snr = _compute_snr(y, y.copy())
    assert snr == float("inf")


def test_snr_noisy_signal():
    rng = np.random.default_rng(42)
    y = rng.uniform(-1, 1, 10000).astype(np.float32)
    noise = rng.normal(0, 0.1, 10000).astype(np.float32)
    snr = _compute_snr(y, y + noise)
    assert 0 < snr < 100


def test_snr_different_lengths():
    y1 = np.ones(1000)
    y2 = np.ones(500)
    snr = _compute_snr(y1, y2)
    assert snr == float("inf")


def test_ext_with_extension():
    assert _ext("file.wav") == ".wav"
    assert _ext("track.flac") == ".flac"


def test_ext_without_extension():
    assert _ext("noextension") == ".audio"
