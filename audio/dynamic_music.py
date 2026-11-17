"""Helpers for mixing layered, dynamic game music.

The module addresses the mix problems in the original design:

* layered stems are summed as amplitudes, so the bus is given headroom
  (:func:`stem_gain`);
* fades last a whole number of beats instead of a fixed 0.2 s, so a Boss
  phase change cannot cut a drum hit in half (:func:`crossfade`,
  :func:`beat_crossfade`);
* loop points are aligned on bar boundaries in the sample domain, which
  keeps bar 8 from drifting after a sample-rate conversion
  (:func:`align_loop`);
* ducking gain is computed once and applied to every bus -- music, voice
  and UI -- rather than only to the music bus (:func:`ducking_gain`,
  :func:`duck_all_buses`);
* only stems that fit the remaining memory budget are selected, so mobile
  scenes do not decode every stem up front (:func:`stream_stems`).
"""

from __future__ import annotations

import math
from typing import Any, Callable, Iterable, Mapping, Sequence

__all__ = [
    "DEFAULT_HEADROOM_DB",
    "DEFAULT_DUCKED_BUSES",
    "stem_gain",
    "crossfade",
    "beat_crossfade",
    "beat_fade_samples",
    "align_loop",
    "ducking_gain",
    "duck_all_buses",
    "stream_stems",
]

DEFAULT_HEADROOM_DB = -6.0
"""Bus headroom in dB; a negative value leaves room below full scale."""

DEFAULT_DUCKED_BUSES: tuple[str, ...] = ("music", "voice", "ui", "sfx")
"""Every bus participates in ducking, not just the music bus."""

_EPS = 1e-9


def _clamp01(value: float) -> float:
    """Clamp ``value`` into the closed interval ``[0, 1]``."""
    return min(1.0, max(0.0, float(value)))


def stem_gain(stem_count: int, headroom_db: float = DEFAULT_HEADROOM_DB) -> float:
    """Return the per-stem gain in dB for a layered bus.

    ``stem_count`` equal-amplitude stems add coherently, raising the bus by
    ``20 * log10(stem_count)`` dB.  Subtracting that from ``headroom_db``
    keeps the summed climax under the requested headroom instead of
    clipping.

    A count of zero (or less) has no meaningful gain contribution and
    yields ``0.0``.
    """
    count = int(stem_count)
    if count <= 0:
        return 0.0
    return float(headroom_db) - 20.0 * math.log10(count)


def crossfade(outgoing: float, incoming: float, position: float) -> float:
    """Linearly crossfade between two gain values.

    ``position`` is normalised to ``[0, 1]`` and clamped, so a fade that
    starts before or runs past its scheduled window never overshoots.
    ``0`` returns ``outgoing``, ``1`` returns ``incoming``.
    """
    t = _clamp01(position)
    start = float(outgoing)
    end = float(incoming)
    return start + (end - start) * t


def beat_crossfade(
    outgoing: float,
    incoming: float,
    elapsed_seconds: float,
    bpm: float,
    *,
    beats: float = 1.0,
) -> float:
    """Crossfade over a whole number of beats.

    ``elapsed_seconds`` is the time since the fade began; the fade duration
    is ``beats * 60 / bpm`` seconds.  Scheduling the start on a beat
    boundary therefore changes layers exactly on the beat and never slices
    a drum transient part-way through a fixed 0.2 s fade.
    """
    if bpm <= 0:
        raise ValueError("bpm must be greater than 0")
    if beats <= 0:
        raise ValueError("beats must be greater than 0")
    duration = beats * 60.0 / float(bpm)
    return crossfade(outgoing, incoming, float(elapsed_seconds) / duration)


def beat_fade_samples(
    bpm: float,
    beats: float = 1.0,
    *,
    sample_rate: float = 48000.0,
) -> int:
    """Return a beat-aligned fade duration as a whole number of samples."""
    if bpm <= 0:
        raise ValueError("bpm must be greater than 0")
    if beats <= 0:
        raise ValueError("beats must be greater than 0")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be greater than 0")
    duration = beats * 60.0 / float(bpm)
    return int(round(duration * float(sample_rate)))


def align_loop(
    loop_point: float,
    bar_length: float,
    *,
    sample_rate: float | None = None,
) -> float:
    """Move ``loop_point`` up to the next bar boundary.

    Loops set mid-bar repeat an extra beat at the crossfade, so the point is
    rounded *up* to a multiple of ``bar_length``.  An already aligned point
    is returned unchanged.

    When ``sample_rate`` is supplied the computation is done on integer
    sample counts.  Aligning in the sample domain after a sample-rate
    conversion prevents the fractional-sample error that otherwise
    accumulates and makes bar 8 drift out of sync.
    """
    bar = float(bar_length)
    if bar <= 0:
        raise ValueError("bar_length must be greater than 0")
    point = float(loop_point)

    if sample_rate is None:
        bars = math.ceil(point / bar - _EPS)
        return float(bars * bar)

    rate = float(sample_rate)
    if rate <= 0:
        raise ValueError("sample_rate must be greater than 0")
    bar_samples = int(round(bar * rate))
    if bar_samples <= 0:
        raise ValueError("bar_length is shorter than one sample")
    loop_samples = int(round(point * rate))
    bars = math.ceil(loop_samples / bar_samples - _EPS)
    return float(bars * bar_samples / rate)


def ducking_gain(
    level_db: float,
    threshold_db: float,
    *,
    ratio: float = 4.0,
    max_reduction_db: float = 24.0,
) -> float:
    """Return the gain in dB a bus should receive while ducking.

    ``level_db`` is the program level that triggers ducking.  At or below
    ``threshold_db`` the bus is untouched and the result is exactly ``0.0``;
    above it the gain is reduced according to ``ratio`` and capped at
    ``max_reduction_db``.  The returned value is always ``<= 0.0``.
    """
    level = float(level_db)
    threshold = float(threshold_db)
    if ratio <= 1.0:
        raise ValueError("ratio must be greater than 1")
    if max_reduction_db < 0:
        raise ValueError("max_reduction_db must not be negative")
    if level <= threshold:
        return 0.0
    reduction = (level - threshold) * (1.0 - 1.0 / float(ratio))
    reduction = min(reduction, float(max_reduction_db))
    return -float(reduction)


def duck_all_buses(
    level_db: float,
    threshold_db: float,
    *,
    buses: Sequence[str] = DEFAULT_DUCKED_BUSES,
    ratio: float = 4.0,
    max_reduction_db: float = 24.0,
) -> dict[str, float]:
    """Return the ducking gain for every bus, not just the music bus.

    Voice and UI cues feed the same sidechain calculation, so the whole mix
    breathes together instead of only the music bed dropping.
    """
    gain = ducking_gain(
        level_db,
        threshold_db,
        ratio=ratio,
        max_reduction_db=max_reduction_db,
    )
    return {bus: gain for bus in buses}


def stream_stems(
    stems: Iterable[Mapping[str, Any]],
    budget_bytes: int | None,
    *,
    decode: Callable[[Mapping[str, Any]], Any] | None = None,
) -> list[dict[str, Any]]:
    """Select the stems that fit within ``budget_bytes``.

    Stems are considered in order and selected while their ``bytes`` fit in
    the remaining budget; stems that do not fit are skipped rather than
    forcing an early stop.  Only the selected descriptors are returned, and
    only those are decoded when ``decode`` is supplied, so mobile scenes no
    longer decode all stems at once.

    ``budget_bytes=None`` means "no budget" and selects every stem.
    """
    selected: list[dict[str, Any]] = []

    if budget_bytes is None:
        selected = [dict(stem) for stem in stems]
    else:
        remaining = max(0, int(budget_bytes))
        for stem in stems:
            try:
                size = max(0, int(stem.get("bytes", 0)))
            except (TypeError, ValueError):
                size = 0
            if size > remaining:
                continue
            remaining -= size
            selected.append(dict(stem))

    if decode is not None:
        for stem in selected:
            stem["data"] = decode(stem)

    return selected
