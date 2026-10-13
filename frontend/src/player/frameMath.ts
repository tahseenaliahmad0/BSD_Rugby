/**
 * Pure frame and time maths for the player. Frame rates are exact rationals (for example
 * 30000/1001) so that 29.97 fps footage steps correctly over a whole match.
 */

export interface Fps {
  num: number;
  den: number;
}

/** Tolerance, in frames, when deciding which frame a media time belongs to. Media
 *  timestamps are rationals rendered as floats, so a frame start such as 1/30 can come
 *  back as 0.03333333333 and multiply to 0.9999999999 instead of 1. */
const FRAME_EPSILON = 1e-3;

export const PLAYBACK_RATES = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2] as const;
export type PlaybackRate = (typeof PLAYBACK_RATES)[number];

export function fpsValue(fps: Fps): number {
  if (fps.den <= 0 || fps.num <= 0) {
    throw new Error('frame rate must be positive');
  }
  return fps.num / fps.den;
}

/** The index of the frame being shown at media time `t` (0-based). */
export function timeToFrame(t: number, fps: Fps): number {
  if (!Number.isFinite(t) || t <= 0) return 0;
  return Math.floor(t * fpsValue(fps) + FRAME_EPSILON);
}

/** The presentation time at which frame `frame` starts. */
export function frameToTime(frame: number, fps: Fps): number {
  return Math.max(0, frame) / fpsValue(fps);
}

/** A time safely inside frame `frame`: its centre. Seeking here never lands on a boundary. */
export function frameCenterTime(frame: number, fps: Fps): number {
  return (Math.max(0, frame) + 0.5) / fpsValue(fps);
}

/** The last valid frame index for a video of `durationS` seconds (or `frameCount` frames). */
export function lastFrameIndex(durationS: number, fps: Fps, frameCount?: number | null): number {
  if (frameCount && frameCount > 0) return frameCount - 1;
  if (!Number.isFinite(durationS) || durationS <= 0) return 0;
  return Math.max(0, Math.ceil(durationS * fpsValue(fps) - FRAME_EPSILON) - 1);
}

/** Time to seek to after stepping `delta` frames from media time `t`, clamped to the video. */
export function stepTime(
  t: number,
  delta: number,
  fps: Fps,
  durationS: number,
  frameCount?: number | null,
): number {
  const last = lastFrameIndex(durationS, fps, frameCount);
  const target = Math.min(last, Math.max(0, timeToFrame(t, fps) + delta));
  return Math.min(frameCenterTime(target, fps), Math.max(0, durationS));
}

/** Clamp a seek to the video, keeping it off the very end so the last frame still shows. */
export function clampTime(t: number, durationS: number): number {
  if (!Number.isFinite(t) || t < 0) return 0;
  if (!Number.isFinite(durationS) || durationS <= 0) return t;
  return Math.min(t, durationS);
}

function pad(n: number, width = 2): string {
  return String(n).padStart(width, '0');
}

/** HH:MM:SS:FF timecode of the frame shown at media time `t`. */
export function formatTimecode(t: number, fps: Fps): string {
  const frame = timeToFrame(t, fps);
  const rate = fpsValue(fps);
  // Timecode frames count within a nominal integer-fps second (e.g. 29.97 shows 0..29).
  const nominal = Math.round(rate);
  const wholeSeconds = Math.floor(frame / rate + FRAME_EPSILON / rate);
  const frameInSecond = Math.min(nominal - 1, frame - Math.floor(wholeSeconds * rate + FRAME_EPSILON));
  const h = Math.floor(wholeSeconds / 3600);
  const m = Math.floor((wholeSeconds % 3600) / 60);
  const s = wholeSeconds % 60;
  return `${pad(h)}:${pad(m)}:${pad(s)}:${pad(frameInSecond)}`;
}

/** Human clock time: M:SS or H:MM:SS, optionally with milliseconds (M:SS.mmm). */
export function formatClock(t: number, withMillis = false): string {
  const safe = Number.isFinite(t) && t > 0 ? t : 0;
  const totalMs = Math.round(safe * 1000);
  const ms = totalMs % 1000;
  const totalS = Math.floor(totalMs / 1000);
  const h = Math.floor(totalS / 3600);
  const m = Math.floor((totalS % 3600) / 60);
  const s = totalS % 60;
  const base = h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
  return withMillis ? `${base}.${pad(ms, 3)}` : base;
}

/** Playback rate one step faster (direction 1) or slower (direction -1). */
export function nextRate(current: number, direction: 1 | -1): PlaybackRate {
  const rates = PLAYBACK_RATES;
  let index = rates.findIndex((r) => Math.abs(r - current) < 1e-9);
  if (index === -1) {
    // Snap an unknown rate to the nearest listed one, then step.
    index = rates.reduce(
      (best, r, i) => (Math.abs(r - current) < Math.abs(rates[best] - current) ? i : best),
      0,
    );
  }
  const next = Math.min(rates.length - 1, Math.max(0, index + direction));
  return rates[next];
}

/** Which thumbnail (1-based) covers media time `t`, given one thumbnail every `intervalS`. */
export function thumbnailIndex(t: number, intervalS: number, count: number): number {
  if (count <= 0 || intervalS <= 0) return 0;
  const index = Math.floor(Math.max(0, t) / intervalS) + 1;
  return Math.min(count, Math.max(1, index));
}

export function thumbnailUrl(template: string, index: number): string {
  return template.replace('{index}', String(index).padStart(5, '0'));
}
