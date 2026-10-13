import { describe, expect, it } from 'vitest';
import {
  clampTime,
  formatClock,
  formatTimecode,
  fpsValue,
  frameCenterTime,
  frameToTime,
  lastFrameIndex,
  nextRate,
  stepTime,
  thumbnailIndex,
  thumbnailUrl,
  timeToFrame,
} from './frameMath';

const FPS30 = { num: 30, den: 1 };
const FPS2997 = { num: 30000, den: 1001 };
const FPS25 = { num: 25, den: 1 };

describe('timeToFrame', () => {
  it('maps the start of each frame to its index at 30 fps', () => {
    for (let f = 0; f < 3000; f++) {
      expect(timeToFrame(f / 30, FPS30)).toBe(f);
    }
  });

  it('tolerates float error at frame boundaries (0.57 * 100 is just under 57)', () => {
    const FPS100 = { num: 100, den: 1 };
    expect(0.57 * 100).toBeLessThan(57);
    expect(timeToFrame(0.57, FPS100)).toBe(57);
    expect(timeToFrame(1 / 30, FPS30)).toBe(1);
    expect(timeToFrame(2 / 30, FPS30)).toBe(2);
  });

  it('does not jump ahead for times just inside a frame', () => {
    expect(timeToFrame(0.033, FPS30)).toBe(0);
    expect(timeToFrame(0.9999, FPS30)).toBe(29);
  });

  it('handles 29.97 fps exactly over a full match', () => {
    const frames = 80 * 60 * 30; // 80 minutes
    for (const f of [0, 1, 29, 30, 1000, 54321, frames - 1]) {
      expect(timeToFrame((f * 1001) / 30000, FPS2997)).toBe(f);
    }
  });

  it('clamps negative and non-finite times to frame 0', () => {
    expect(timeToFrame(-1, FPS30)).toBe(0);
    expect(timeToFrame(Number.NaN, FPS30)).toBe(0);
  });
});

describe('frameToTime and frameCenterTime', () => {
  it('round-trips through timeToFrame', () => {
    for (const fps of [FPS30, FPS2997, FPS25]) {
      for (const f of [0, 1, 7, 100, 12345]) {
        expect(timeToFrame(frameToTime(f, fps), fps)).toBe(f);
        expect(timeToFrame(frameCenterTime(f, fps), fps)).toBe(f);
      }
    }
  });

  it('puts the centre half a frame after the start', () => {
    expect(frameCenterTime(0, FPS25)).toBeCloseTo(0.02, 10);
    expect(frameCenterTime(10, FPS25)).toBeCloseTo(0.42, 10);
  });
});

describe('lastFrameIndex', () => {
  it('prefers the known frame count', () => {
    expect(lastFrameIndex(10, FPS30, 300)).toBe(299);
  });
  it('derives it from the duration otherwise', () => {
    expect(lastFrameIndex(10, FPS30)).toBe(299);
    expect(lastFrameIndex(10.005, FPS30)).toBe(300);
    expect(lastFrameIndex(0, FPS30)).toBe(0);
  });
});

describe('stepTime', () => {
  it('steps one frame forward and back, landing in the frame centre', () => {
    const t1 = stepTime(0, 1, FPS30, 10, 300);
    expect(timeToFrame(t1, FPS30)).toBe(1);
    expect(t1).toBeCloseTo(1.5 / 30, 10);
    const t0 = stepTime(t1, -1, FPS30, 10, 300);
    expect(timeToFrame(t0, FPS30)).toBe(0);
  });

  it('walks every frame of a 29.97 fps clip without skipping or repeating', () => {
    let t = 0;
    const seen: number[] = [];
    for (let i = 0; i < 200; i++) {
      seen.push(timeToFrame(t, FPS2997));
      t = stepTime(t, 1, FPS2997, 100, null);
    }
    expect(seen).toEqual(Array.from({ length: 200 }, (_, i) => i));
  });

  it('clamps at the start and end of the video', () => {
    expect(stepTime(0, -5, FPS30, 10, 300)).toBeCloseTo(0.5 / 30, 10);
    const end = stepTime(9.99, 50, FPS30, 10, 300);
    expect(timeToFrame(end, FPS30)).toBe(299);
    expect(end).toBeLessThanOrEqual(10);
  });

  it('supports multi-frame jumps', () => {
    expect(timeToFrame(stepTime(1, 10, FPS30, 10, 300), FPS30)).toBe(40);
  });
});

describe('formatTimecode', () => {
  it('formats HH:MM:SS:FF at 30 fps', () => {
    expect(formatTimecode(0, FPS30)).toBe('00:00:00:00');
    expect(formatTimecode(1 / 30, FPS30)).toBe('00:00:00:01');
    expect(formatTimecode(1, FPS30)).toBe('00:00:01:00');
    expect(formatTimecode(61.5, FPS30)).toBe('00:01:01:15');
    expect(formatTimecode(3600 + 59 * 60 + 59 + 29 / 30, FPS30)).toBe('01:59:59:29');
  });

  it('never shows a frame number equal to the nominal rate at 29.97 fps', () => {
    for (let f = 0; f < 30 * 60 * 5; f++) {
      const tc = formatTimecode((f * 1001) / 30000, FPS2997);
      expect(Number(tc.slice(-2))).toBeLessThan(30);
    }
  });
});

describe('formatClock', () => {
  it('formats minutes and seconds', () => {
    expect(formatClock(0)).toBe('0:00');
    expect(formatClock(65)).toBe('1:05');
    expect(formatClock(3725)).toBe('1:02:05');
  });
  it('adds milliseconds when asked', () => {
    expect(formatClock(1.2345, true)).toBe('0:01.235');
    expect(formatClock(0.0005, true)).toBe('0:00.001');
  });
  it('treats bad input as zero', () => {
    expect(formatClock(Number.NaN)).toBe('0:00');
    expect(formatClock(-3)).toBe('0:00');
  });
});

describe('nextRate', () => {
  it('steps through the allowed rates and stops at the ends', () => {
    expect(nextRate(1, 1)).toBe(1.25);
    expect(nextRate(1, -1)).toBe(0.75);
    expect(nextRate(2, 1)).toBe(2);
    expect(nextRate(0.25, -1)).toBe(0.25);
  });
  it('snaps unknown rates to the nearest listed one first', () => {
    expect(nextRate(1.1, 1)).toBe(1.25);
    expect(nextRate(0.9, -1)).toBe(0.75);
  });
});

describe('thumbnails', () => {
  it('picks the sheet covering the time, 1-based and clamped', () => {
    expect(thumbnailIndex(0, 10, 5)).toBe(1);
    expect(thumbnailIndex(9.99, 10, 5)).toBe(1);
    expect(thumbnailIndex(10, 10, 5)).toBe(2);
    expect(thumbnailIndex(999, 10, 5)).toBe(5);
    expect(thumbnailIndex(5, 10, 0)).toBe(0);
  });
  it('builds zero-padded urls', () => {
    expect(thumbnailUrl('/media/proxies/x/thumbs/{index}.jpg', 7)).toBe(
      '/media/proxies/x/thumbs/00007.jpg',
    );
  });
});

describe('misc', () => {
  it('fpsValue rejects bad rates', () => {
    expect(() => fpsValue({ num: 0, den: 1 })).toThrow();
    expect(fpsValue(FPS2997)).toBeCloseTo(29.97003, 5);
  });
  it('clampTime keeps seeks inside the video', () => {
    expect(clampTime(-1, 10)).toBe(0);
    expect(clampTime(11, 10)).toBe(10);
    expect(clampTime(5, 10)).toBe(5);
  });
});
