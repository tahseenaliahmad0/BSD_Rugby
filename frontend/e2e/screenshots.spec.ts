/**
 * Captures the screenshots used by the coach guides in docs/guides. Not part of the normal
 * test run: `SCREENSHOTS=1 npx playwright test e2e/screenshots.spec.ts`.
 * Takes each coach screen at laptop width and at tablet width.
 */
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'docs', 'guides', 'images');
const ADMIN = { email: 'admin@example.com', password: 'admin-password-123' };

test.skip(!process.env.SCREENSHOTS, 'set SCREENSHOTS=1 to refresh the guide images');

async function login(page: Page) {
  await page.goto('/login');
  await page.getByTestId('login-email').fill(ADMIN.email);
  await page.getByTestId('login-password').fill(ADMIN.password);
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('squad-switcher')).toBeVisible();
}

async function csrf(page: Page) {
  return (await page.context().cookies()).find((c) => c.name === 'rugby_csrf')!.value;
}

async function shot(page: Page, name: string) {
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: false });
}

test('capture guide screenshots', async ({ page }) => {
  mkdirSync(OUT, { recursive: true });
  await page.setViewportSize({ width: 1280, height: 860 });
  await login(page);
  const squads = await (await page.request.get('/api/squads')).json();
  const squadId = squads[0].id as string;
  const events = await (await page.request.get(`/api/squads/${squadId}/events`)).json();
  const eventId = events[0].id as string;
  const token = await csrf(page);

  // Seed a few tags through the API so the screens have content.
  const existing = await (await page.request.get(`/api/events/${eventId}/tags`)).json();
  if (existing.length === 0) {
    const players = await (await page.request.get(`/api/squads/${squadId}/players`)).json();
    const p = (n: number) => players.find((x: { shirt_number: number }) => x.shirt_number === n)?.id;
    const create = [
      { code: 'Kickoff', start_ms: 0, end_ms: 2500, descriptors: { team: 'Us', zone: 'Own half' } },
      { code: 'Scrum', start_ms: 1500, end_ms: 4000, descriptors: { outcome: 'Won', zone: 'Opp half', team: 'Us' } },
      { code: 'Lineout', start_ms: 4500, end_ms: 7000, descriptors: { outcome: 'Lost', zone: 'Opp 22', team: 'Us' }, note: 'Overthrown at the back' },
      { code: 'Carry', start_ms: 5000, end_ms: 6500, descriptors: { zone: 'Opp 22' }, player_ids: [p(10)].filter(Boolean) },
      { code: 'Tackle', start_ms: 7500, end_ms: 9500, descriptors: { tackle: 'Dominant', zone: 'Own half' }, player_ids: [p(2)].filter(Boolean) },
      { code: 'Try', start_ms: 9000, end_ms: 12000, descriptors: { team: 'Us' }, player_ids: [p(15)].filter(Boolean) },
    ];
    await page.request.post(`/api/events/${eventId}/tags/batch`, { headers: { 'X-CSRF-Token': token }, data: { create } });
  }

  await page.goto(`/squads/${squadId}`);
  await expect(page.getByTestId('event-card').first()).toBeVisible();
  await shot(page, 'library');

  await page.goto(`/matches/${eventId}`);
  await expect(page.getByTestId('player')).toBeVisible();
  await shot(page, 'match');

  await page.goto(`/matches/${eventId}/tag`);
  await expect(page.getByTestId('code-Scrum')).toBeVisible();
  await page.waitForTimeout(800);
  await shot(page, 'tagging-workspace');
  await page.getByTestId('timeline').scrollIntoViewIfNeeded();
  const box = (await page.getByTestId('timeline').locator('canvas').boundingBox())!;
  await page.mouse.click(box.x + 128 + (5500 * (box.width - 128)) / 60_000, box.y + 26 + 2 * 30 + 15);
  await page.waitForTimeout(300);
  await shot(page, 'tagging-timeline');

  await page.goto(`/squads/${squadId}/clips`);
  await expect(page.getByTestId('chip-code-Lineout')).toBeVisible();
  await page.getByTestId('chip-code-Lineout').click();
  await page.getByTestId('chip-outcome-Lost').click();
  await expect(page.getByTestId('clip-count')).toContainText('1 clip');
  await shot(page, 'find-clips');
  await page.getByTestId('clip-card').first().click();
  await expect(page.getByTestId('clip-player-panel')).toBeVisible();
  await shot(page, 'find-clips-watch');

  // A playlist from the search.
  await page.getByTestId('chip-outcome-Lost').click();
  await page.getByTestId('chip-code-Lineout').click();
  await expect(page.getByTestId('clip-count')).toContainText('6 clips');
  await page.getByTestId('add-to-playlist').last().click();
  await page.getByTestId('new-playlist-name').fill('Attack highlights');
  await page.getByTestId('new-playlist-create').click();
  await expect(page.getByTestId('playlist-title')).toHaveText('Attack highlights');
  await shot(page, 'playlist');

  await page.goto(`/squads/${squadId}/playlists`);
  await expect(page.getByTestId('playlist-card').first()).toBeVisible();
  await shot(page, 'playlists');

  await page.goto(`/squads/${squadId}/stats`);
  await expect(page.getByTestId('codes-table')).toContainText('Lineout');
  await shot(page, 'stats');

  await page.goto(`/squads/${squadId}/templates`);
  await expect(page.getByTestId('template-card').first()).toBeVisible();
  await page.getByTestId('template-card').first().click();
  await expect(page.getByTestId('button-row').first()).toBeVisible();
  await shot(page, 'template-editor');

  // Tablet width for the coach screens.
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto(`/squads/${squadId}/clips`);
  await expect(page.getByTestId('chip-code-Lineout')).toBeVisible();
  await shot(page, 'find-clips-tablet');
  const playlists = await (await page.request.get(`/api/squads/${squadId}/playlists`)).json();
  await page.goto(`/playlists/${playlists[0].id}`);
  await expect(page.getByTestId('playlist-title')).toBeVisible();
  await shot(page, 'playlist-tablet');
  await page.setViewportSize({ width: 820, height: 1180 });
  await page.goto(`/squads/${squadId}/stats`);
  await expect(page.getByTestId('codes-table')).toBeVisible();
  await shot(page, 'stats-tablet-portrait');
  await page.goto(`/playlists/${playlists[0].id}`);
  await expect(page.getByTestId('playlist-title')).toBeVisible();
  await shot(page, 'playlist-tablet-portrait');
});
