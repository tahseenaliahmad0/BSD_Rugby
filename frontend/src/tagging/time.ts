/**
 * Conversions between video time and the event timeline (ADR 0006).
 * Every stored time is an integer millisecond on the event timeline; a video starts on that
 * timeline at `offsetMs`. Frame snapping goes through the exact rational frame rate.
 */
import { frameToTime, timeToFrame, type Fps } from '../player/frameMath';

export function videoSecondsToEventMs(seconds: number, offsetMs: number): number {
  return Math.round(seconds * 1000) + offsetMs;
}

export function eventMsToVideoSeconds(ms: number, offsetMs: number): number {
  return (ms - offsetMs) / 1000;
}

/** The start of the frame shown at `seconds`. */
export function snapSecondsToFrame(seconds: number, fps: Fps): number {
  return frameToTime(timeToFrame(Math.max(0, seconds), fps), fps);
}

/**
 * The frame an event-timeline millisecond belongs to. A frame start rounded to a whole
 * millisecond can sit up to half a millisecond before the true boundary, so that much
 * tolerance (in frames) is allowed before flooring.
 */
export function eventMsToFrame(ms: number, offsetMs: number, fps: Fps): number {
  const seconds = eventMsToVideoSeconds(ms, offsetMs);
  if (seconds <= 0) return 0;
  const rate = fps.num / fps.den;
  return Math.floor(seconds * rate + 0.0005 * rate + 1e-6);
}

/** Snap an event-timeline time to the (millisecond-rounded) start of its video frame. */
export function snapEventMsToFrame(ms: number, offsetMs: number, fps: Fps): number {
  return frameToEventMs(eventMsToFrame(ms, offsetMs, fps), offsetMs, fps);
}

export function frameToEventMs(frame: number, offsetMs: number, fps: Fps): number {
  return videoSecondsToEventMs(frameToTime(frame, fps), offsetMs);
}

/** One frame, in milliseconds (fractional for 29.97 fps). */
export function frameDurationMs(fps: Fps): number {
  return (1000 * fps.den) / fps.num;
}

export function clampMs(ms: number, minMs: number, maxMs: number): number {
  return Math.min(maxMs, Math.max(minMs, Math.round(ms)));
}

/** m:ss or h:mm:ss for an event-timeline time, with optional tenths. */
export function formatMs(ms: number, tenths = false): string {
  const totalTenths = Math.max(0, Math.round(ms / 100));
  const totalS = Math.floor(totalTenths / 10);
  const h = Math.floor(totalS / 3600);
  const m = Math.floor((totalS % 3600) / 60);
  const s = totalS % 60;
  const base = h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
  return tenths ? `${base}.${totalTenths % 10}` : base;
}
