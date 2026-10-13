"""Conversions between video time and the event timeline (ADR 0006).

Every stored time on the event timeline is an integer number of milliseconds. A video sits on
that timeline at `offset_ms`, so video seconds and event milliseconds convert as below.
"""

from __future__ import annotations

from fractions import Fraction


def video_seconds_to_event_ms(seconds: float, offset_ms: int) -> int:
    """Event-timeline milliseconds for a video-relative time in seconds."""
    return round(seconds * 1000) + offset_ms


def event_ms_to_video_seconds(ms: int, offset_ms: int) -> float:
    """Video-relative seconds for an event-timeline time."""
    return (ms - offset_ms) / 1000


def frame_index(seconds: float, fps: Fraction) -> int:
    """The frame shown at `seconds` (0-based).

    Times that came through integer milliseconds can sit up to half a millisecond before the
    true frame boundary, so that much tolerance (expressed in frames) is allowed.
    """
    if seconds <= 0:
        return 0
    rate = fps.numerator / fps.denominator
    return int(seconds * rate + 0.0005 * rate + 1e-6)


def snap_to_frame(seconds: float, fps: Fraction) -> float:
    """The start time of the frame shown at `seconds`."""
    return frame_index(seconds, fps) * fps.denominator / fps.numerator


def snap_event_ms_to_frame(ms: int, offset_ms: int, fps: Fraction) -> int:
    """Snap an event-timeline time to the start of the video frame it falls in."""
    seconds = event_ms_to_video_seconds(ms, offset_ms)
    return video_seconds_to_event_ms(snap_to_frame(max(0.0, seconds), fps), offset_ms)


def clamp_range(start_ms: int, end_ms: int, *, min_length_ms: int = 0) -> tuple[int, int]:
    """Order a range and make sure it is at least `min_length_ms` long."""
    lo, hi = (start_ms, end_ms) if start_ms <= end_ms else (end_ms, start_ms)
    lo = max(0, lo)
    hi = max(lo + min_length_ms, hi)
    return lo, hi
