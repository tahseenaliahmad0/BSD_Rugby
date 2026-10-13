import { execFileSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';

const ADMIN = { email: 'admin@example.com', password: 'admin-password-123' };

let clipPath: string;

test.beforeAll(() => {
  // A 4 second synthetic clip from FFmpeg so the test needs no real footage.
  const dir = mkdtempSync(join(tmpdir(), 'rugby-e2e-clip-'));
  clipPath = join(dir, 'smoke clip.mp4');
  execFileSync('ffmpeg', [
    '-hide_banner', '-v', 'error', '-y',
    '-f', 'lavfi', '-i', 'testsrc=size=640x360:rate=25:duration=4',
    '-f', 'lavfi', '-i', 'sine=frequency=440:duration=4',
    '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest',
    clipPath,
  ]);
});

async function login(page: Page) {
  await page.goto('/login');
  await page.getByTestId('login-email').fill(ADMIN.email);
  await page.getByTestId('login-password').fill(ADMIN.password);
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('squad-switcher')).toBeVisible();
}

test('login, create a match, upload a video and play it frame by frame', async ({ page }) => {
  await login(page);

  // The seeded demo squad is selected and lists the demo match.
  await expect(page.getByTestId('squad-switcher')).toHaveValue('Demo Squad');
  await expect(page.getByTestId('event-card').first()).toContainText('Demo match');

  // Create a new match.
  await page.getByTestId('new-match').click();
  await page.getByTestId('match-date').fill('2026-10-10');
  await page.getByTestId('match-opponent').fill('Smoke Test RFC');
  await page.getByTestId('match-create').click();
  await expect(page.getByTestId('match-title')).toHaveText('vs Smoke Test RFC');

  // Upload the clip over tus; the API transcodes it inline for the test.
  await page.getByTestId('upload-input').setInputFiles(clipPath);
  await expect(page.getByTestId('upload-progress')).toBeVisible();
  await expect(page.getByTestId('video-status')).toHaveText('Ready', { timeout: 90_000 });

  // The player shows the right frame rate and plays.
  const player = page.getByTestId('player');
  await expect(player).toBeVisible();
  await expect(page.getByTestId('player-frame')).toContainText('25.00 fps');
  await expect(page.getByTestId('player-frame')).toContainText('of 100');

  const video = page.getByTestId('player-video');
  const canPlayH264 = await video.evaluate(
    (v: HTMLVideoElement) => v.canPlayType('video/mp4; codecs="avc1.640028, mp4a.40.2"') !== '',
  );
  if (canPlayH264) {
    await page.getByTestId('player-play').click();
    await expect
      .poll(async () => video.evaluate((v: HTMLVideoElement) => v.currentTime))
      .toBeGreaterThan(0.5);
    await page.getByTestId('player-play').click();
    await expect.poll(async () => video.evaluate((v: HTMLVideoElement) => v.paused)).toBe(true);

    // Frame stepping with the keyboard moves exactly one frame at a time.
    const frameNumber = async () => {
      const text = await page.getByTestId('player-frame').textContent();
      return Number(/Frame (\d+)/.exec(text ?? '')?.[1]);
    };
    await page.keyboard.press('Home');
    await expect.poll(frameNumber).toBe(0);
    await page.keyboard.press('ArrowRight');
    await expect.poll(frameNumber).toBe(1);
    await page.keyboard.press('ArrowRight');
    await expect.poll(frameNumber).toBe(2);
    await page.keyboard.press('ArrowLeft');
    await expect.poll(frameNumber).toBe(1);
    await expect
      .poll(async () => video.evaluate((v: HTMLVideoElement) => v.currentTime))
      .toBeCloseTo(1.5 / 25, 3);
  } else {
    // Playwright's open-source Chromium has no H.264 decoder; CI runs this with Google Chrome.
    test.info().annotations.push({
      type: 'skipped-check',
      description: 'This browser cannot decode H.264, so playback and frame stepping were not checked.',
    });
    await expect.poll(async () => video.evaluate((v: HTMLVideoElement) => v.error?.code ?? 0)).toBe(4);
  }

  // Speed control works even without a decoder.
  await page.keyboard.press('l');
  await expect.poll(async () => video.evaluate((v: HTMLVideoElement) => v.playbackRate)).toBe(1.25);

  // The library now shows the new match with its video.
  await page.getByRole('link', { name: 'Back to library' }).click();
  const card = page.getByTestId('event-card').filter({ hasText: 'Smoke Test RFC' });
  await expect(card).toContainText('1 video');

  // Sign out and confirm the session is gone.
  await page.getByTestId('user-menu').click();
  await page.getByTestId('logout').click();
  await expect(page.getByTestId('login-submit')).toBeVisible();
  await page.goto('/');
  await expect(page.getByTestId('login-submit')).toBeVisible();
});

test('a wrong password is refused with a plain message', async ({ page }) => {
  await page.goto('/login');
  await page.getByTestId('login-email').fill(ADMIN.email);
  await page.getByTestId('login-password').fill('not-the-password');
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('login-error')).toContainText('do not match');
});
