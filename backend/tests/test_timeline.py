"""Time conversions between video seconds and event-timeline milliseconds (ADR 0006)."""

from __future__ import annotations

from fractions import Fraction

from app.services.timeline import (
    clamp_range,
    event_ms_to_video_seconds,
    frame_index,
    snap_event_ms_to_frame,
    snap_to_frame,
    video_seconds_to_event_ms,
)

FPS30 = Fraction(30, 1)
FPS2997 = Fraction(30000, 1001)


def test_video_to_event_and_back_with_offset() -> None:
    assert video_seconds_to_event_ms(12.345, 5000) == 17345
    assert event_ms_to_video_seconds(17345, 5000) == 12.345
    assert video_seconds_to_event_ms(0.0, 0) == 0
    # A second camera that started 90 s after the first maps the same moment to the same ms.
    assert video_seconds_to_event_ms(10.0, 90_000) == video_seconds_to_event_ms(100.0, 0)


def test_rounding_is_to_the_nearest_millisecond() -> None:
    assert video_seconds_to_event_ms(1.0004, 0) == 1000
    assert video_seconds_to_event_ms(1.0006, 0) == 1001


def test_frame_index_tolerates_float_error() -> None:
    assert frame_index(1 / 30, FPS30) == 1
    assert frame_index(0.57, Fraction(100)) == 57
    assert frame_index(-1, FPS30) == 0
    for f in (0, 1, 29, 30, 1000, 54321):
        assert frame_index(f * 1001 / 30000, FPS2997) == f


def test_snap_to_frame_start() -> None:
    assert snap_to_frame(0.05, FPS30) == 1 / 30
    assert abs(snap_to_frame(2.0, FPS2997) - 59 * 1001 / 30000) < 1e-9


def test_snap_event_ms_lands_on_the_frame_start() -> None:
    # 7 s into a video that starts at 3 s on the event timeline, at 29.97 fps.
    ms = snap_event_ms_to_frame(10_020, 3000, FPS2997)
    seconds = event_ms_to_video_seconds(ms, 3000)
    assert frame_index(seconds, FPS2997) == frame_index(7.02, FPS2997)
    assert abs(seconds - snap_to_frame(7.02, FPS2997)) < 0.001
    assert snap_event_ms_to_frame(-500, 0, FPS30) == 0


def test_clamp_range_orders_and_enforces_minimum_length() -> None:
    assert clamp_range(5000, 2000) == (2000, 5000)
    assert clamp_range(-100, 50) == (0, 50)
    assert clamp_range(1000, 1000, min_length_ms=40) == (1000, 1040)
