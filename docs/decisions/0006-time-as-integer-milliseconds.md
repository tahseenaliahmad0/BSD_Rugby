# 0006. Times on the event timeline are integer milliseconds

Status: accepted. Date: 2026-10-13. Supersedes the float seconds used in migration 0001.

## Context

Tags, playlist ranges, live presses and imports all land on an event's timeline, and each
video carries an offset onto it. Floats make equality and sorting fragile and invite drift
when values are added and rounded in several places.

## Decision

- Every stored time on the event timeline is an integer number of milliseconds:
  `tags.start_ms`, `tags.end_ms`, `videos.offset_ms`, `playlist_items.start_ms`,
  `drawings.timestamp_ms`, `live_tags.lead_ms`, `import_batches.alignment_offset_ms`.
  Suggestions store video-relative milliseconds (the video's offset maps them).
- Conversions live in one place on each side (`backend/app/services/timeline.py`,
  `frontend/src/tagging/time.ts`): video seconds -> event ms is
  `round(seconds * 1000) + offset_ms`; event ms -> video seconds is `(ms - offset_ms) / 1000`.
- The player snaps a time to a frame before converting: frame index from the exact rational
  frame rate, then the frame start in seconds, then milliseconds. At 29.97 fps a frame start
  is not a whole millisecond; the sub-millisecond rounding is far below a frame (33 ms) and
  the frame-index maths tolerate it (ADR 0005).
- Lead and lag on template buttons are milliseconds too.

## Consequences

Milestone 1 API fields change (`offset_s` -> `offset_ms`); no production data existed yet.
Millisecond integers fit a 32-bit column (24 days). Exports and FFmpeg get seconds by
dividing by 1000 at the boundary.
