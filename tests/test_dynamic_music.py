import pytest

from audio.dynamic_music import (
    stem_gain,
    crossfade,
    align_loop,
    ducking_gain,
    stream_stems
)


def test_gain_headroom():
    assert stem_gain(4, -6) <= 0.0

def test_gain_single():
    assert stem_gain(1, 0) == 0.0

def test_crossfade_0():
    assert crossfade(1.0, 2.0, 0.0) == 1.0

def test_crossfade_1():
    assert crossfade(1.0, 2.0, 1.0) == 2.0

def test_crossfade_half():
    assert crossfade(1.0, 2.0, 0.5) == pytest.approx(1.5)

def test_align_loop():
    assert align_loop(3.0, 4.0) == 4.0

def test_align_aligned():
    assert align_loop(4.0, 4.0) == 4.0

def test_duck_under():
    assert ducking_gain(-30.0, -20.0) == 0.0

def test_duck_over():
    assert ducking_gain(-10.0, -20.0) < 0.0

def test_stream_budget():
    assert len(stream_stems([{'id': 'a', 'bytes': 10}, {'id': 'b', 'bytes': 20}], 25)) == 1

def test_stream_all():
    assert len(stream_stems([{'id': 'a', 'bytes': 10}], 100)) == 1

def test_stream_empty():
    assert stream_stems([], 10) == []

def test_gain_zero():
    assert stem_gain(0, 0) == 0.0

def test_crossfade_clamp():
    assert crossfade(1.0, 2.0, -0.2) == 1.0

def test_duck_zero():
    assert ducking_gain(0.0, -20.0) < 0.0
