# 0005. Frame-accurate player on the HTML5 video element

Status: accepted. Date: 2026-10-13.

## Context

Analysts step frames; coaches scrub. Browsers do not guarantee frame-exact
seeking. The spec asks for `requestVideoFrameCallback` and a proxy with a
keyframe at least every second.

## Decision

- Proxies are constant-frame-rate H.264 with `-g <fps>` and
  `force_key_frames` every second, `+faststart`, capped at 1080p.
- The API stores the proxy frame rate as an exact rational (`fps_num`,
  `fps_den`), its duration and frame count.
- The player reads displayed time from `requestVideoFrameCallback`'s
  `mediaTime` when available and falls back to `timeupdate` otherwise.
- Frame stepping pauses, computes the current frame index from the displayed
  time, and seeks to the centre of the target frame (`(n + 0.5) / fps`) so
  that rounding never lands on a frame boundary.
- Keyboard: K or Space play/pause; L play faster (to 2x); J play slower (to
  0.25x); Left/Right one frame; Shift+Left/Right 5 s; Home/End; F fullscreen;
  M mute. Shortcuts are shown in tooltips.

## Consequences

A step can still land one frame off on some browsers after a seek; the frame
number shown comes from the reported media time, so it is honest about what is
on screen. A WebCodecs decoder can be added later for exact stepping.
