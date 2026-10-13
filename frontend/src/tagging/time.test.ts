import { describe, expect, it } from 'vitest';
import {
  clampMs,
  eventMsToFrame,
  eventMsToVideoSeconds,
  formatMs,
  frameDurationMs,
  frameToEventMs,
  snapEventMsToFrame,
  snapSecondsToFrame,
  videoSecondsToEventMs,
} from './time';

const FPS30 = { num: 30, den: 1 };
const FPS2997 = { num: 30000, den: 1001 };

describe('video time <-> event time', () => {
  it('adds the video offset and rounds to the millisecond', () => {
    expect(videoSecondsToEventMs(12.345, 5000)).toBe(17345);
    expect(videoSecondsToEventMs(1.0004, 0)).toBe(1000);
    expect(videoSecondsToEventMs(1.0006, 0)).toBe(1001);
    expect(eventMsToVideoSeconds(17345, 5000)).toBeCloseTo(12.345, 10);
  });

  it('maps the same moment from two cameras to the same event time', () => {
    expect(videoSecondsToEventMs(10, 90_000)).toBe(videoSecondsToEventMs(100, 0));
  });

  it('allows a negative video time for an event time before the video started', () => {
    expect(eventMsToVideoSeconds(1000, 5000)).toBe(-4);
  });
});

describe('frame snapping', () => {
  it('snaps a time to the start of its frame', () => {
    expect(snapSecondsToFrame(0.05, FPS30)).toBeCloseTo(1 / 30, 12);
    expect(snapSecondsToFrame(-2, FPS30)).toBe(0);
  });

  it('snaps an event time to a frame of a video with an offset at 29.97 fps', () => {
    const ms = snapEventMsToFrame(10_020, 3000, FPS2997);
    const seconds = eventMsToVideoSeconds(ms, 3000);
    expect(eventMsToFrame(ms, 3000, FPS2997)).toBe(eventMsToFrame(10_020, 3000, FPS2997));
    expect(Math.abs(seconds - snapSecondsToFrame(7.02, FPS2997))).toBeLessThan(0.001);
  });

  it('round-trips frame numbers through event milliseconds for a full match', () => {
    for (const fps of [FPS30, FPS2997]) {
      for (const frame of [0, 1, 29, 30, 1799, 54_000, 144_000]) {
        expect(eventMsToFrame(frameToEventMs(frame, 12_345, fps), 12_345, fps)).toBe(frame);
      }
    }
  });

  it('knows a frame length in milliseconds', () => {
    expect(frameDurationMs(FPS30)).toBeCloseTo(33.333, 3);
    expect(frameDurationMs(FPS2997)).toBeCloseTo(33.367, 3);
  });
});

describe('helpers', () => {
  it('clamps and rounds', () => {
    expect(clampMs(-5.4, 0, 100)).toBe(0);
    expect(clampMs(150, 0, 100)).toBe(100);
    expect(clampMs(49.6, 0, 100)).toBe(50);
  });

  it('formats event times', () => {
    expect(formatMs(0)).toBe('0:00');
    expect(formatMs(65_000)).toBe('1:05');
    expect(formatMs(3_725_400, true)).toBe('1:02:05.4');
    expect(formatMs(-10)).toBe('0:00');
  });
});
