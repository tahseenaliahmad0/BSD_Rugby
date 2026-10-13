/**
 * Milestone 2 scenario: tag the demo match with hotkeys, fix a tag on the timeline, undo,
 * split, find the clips, build a playlist, play through it, export it, and read the stats.
 */
import { expect, test, type Page } from '@playwright/test';

const ADMIN = { email: 'admin@example.com', password: 'admin-password-123' };

async function login(page: Page) {
  await page.goto('/login');
  await page.getByTestId('login-email').fill(ADMIN.email);
  await page.getByTestId('login-password').fill(ADMIN.password);
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('squad-switcher')).toBeVisible();
}

async function tags(page: Page, eventId: string) {
  const response = await page.request.get(`/api/events/${eventId}/tags`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as Array<{ id: string; code: string; start_ms: number; end_ms: number; descriptors: Record<string, unknown>; version: number }>;
}

test('tag with hotkeys, fix on the timeline, find clips, build and play a playlist, export, stats', async ({ page }) => {
  await login(page);

  // Open the seeded demo match and the tagging workspace.
  await page.getByTestId('event-card').filter({ hasText: 'Demo match' }).click();
  await expect(page.getByTestId('match-title')).toHaveText('Demo match');
  const eventId = page.url().split('/matches/')[1];
  await page.getByTestId('tag-match').click();
  await expect(page.getByTestId('tagging-title')).toContainText('Demo match');
  await expect(page.getByTestId('code-Scrum')).toBeVisible();
  await page.getByTestId('player').click({ position: { x: 5, y: 5 } }); // focus the page, not a field
  await page.keyboard.press('Escape');

  // A start/stop code: press 2 at 0 s, move 5 s on, press 2 again.
  await page.keyboard.press('2');
  await expect(page.getByTestId('code-Scrum')).toHaveAttribute('aria-pressed', 'true');
  await page.keyboard.press('Shift+ArrowRight');
  await page.keyboard.press('2');
  await expect(page.getByTestId('code-Scrum')).toHaveAttribute('aria-pressed', 'false');
  await expect.poll(async () => (await tags(page, eventId)).length).toBe(1);
  let [scrum] = await tags(page, eventId);
  expect(scrum.code).toBe('Scrum');
  expect(scrum.start_ms).toBe(0);
  expect(scrum.end_ms).toBe(5000);

  // An instant code with lead and lag around the playhead (5 s): Tackle = 3 s before, 3 s after.
  await page.keyboard.press('t');
  await expect.poll(async () => (await tags(page, eventId)).length).toBe(2);
  let tackle = (await tags(page, eventId)).find((t) => t.code === 'Tackle')!;
  expect(tackle.start_ms).toBe(2000);
  expect(tackle.end_ms).toBe(8000);

  // Descriptors go on the latest tag: Shift+D marks the tackle as Made; the chip lights up.
  await page.keyboard.press('Shift+D');
  await expect(page.getByTestId('descriptor-tackle-Made')).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(async () => (await tags(page, eventId)).find((t) => t.code === 'Tackle')!.descriptors.tackle).toBe('Made');
  // Shift+A sets the outcome through the chip for the Scrum once it is selected.
  await page.getByTestId('descriptor-zone-Opp 22').click();
  await expect.poll(async () => (await tags(page, eventId)).find((t) => t.code === 'Tackle')!.descriptors.zone).toBe('Opp 22');

  // Pick a player by shirt number.
  await page.getByTestId('player-picker').click();
  await page.getByTestId('player-picker').fill('10');
  await page.getByRole('option', { name: /10/ }).first().click();
  await page.keyboard.press('Escape');
  await expect.poll(async () => (await tags(page, eventId)).find((t) => t.code === 'Tackle')!.descriptors).toBeDefined();

  // Fix the tackle on the timeline: drag its body 2 seconds to the right (frame snapped).
  const timeline = page.getByTestId('timeline');
  const box = (await timeline.boundingBox())!;
  const GUTTER = 128, RULER = 26, ROW_H = 30;
  const pxPerMs = (box.width - GUTTER) / 60_000; // the timeline fits 60 s at first
  const tackleRow = 8; // Tackle is the ninth button of the 15s template
  const y = box.y + RULER + tackleRow * ROW_H + ROW_H / 2;
  const xCentre = box.x + GUTTER + 5000 * pxPerMs;
  await page.mouse.move(xCentre, y);
  await page.mouse.down();
  await page.mouse.move(xCentre + 1000 * pxPerMs, y, { steps: 5 });
  await page.mouse.move(xCentre + 2000 * pxPerMs, y, { steps: 5 });
  await page.mouse.up();
  await expect.poll(async () => (await tags(page, eventId)).find((t) => t.code === 'Tackle')!.start_ms).toBeGreaterThan(3500);
  tackle = (await tags(page, eventId)).find((t) => t.code === 'Tackle')!;
  expect(tackle.end_ms - tackle.start_ms).toBe(6000);
  expect(tackle.start_ms % 1).toBe(0);

  // Undo puts it back; redo moves it again.
  await page.keyboard.press('Control+z');
  await expect.poll(async () => (await tags(page, eventId)).find((t) => t.code === 'Tackle')!.start_ms).toBe(2000);
  await page.keyboard.press('Control+y');
  await expect.poll(async () => (await tags(page, eventId)).find((t) => t.code === 'Tackle')!.start_ms).toBeGreaterThan(3500);

  // Split the scrum at the playhead (5 s is its end; move the playhead to 2.5 s first).
  await page.keyboard.press('Home');
  await page.keyboard.press('Shift+ArrowRight');
  await page.keyboard.press('Shift+ArrowLeft');
  for (let i = 0; i < 2; i++) await page.keyboard.press('Shift+ArrowRight');
  // playhead now 10 s: back to 2.5 s using the timeline ruler
  await page.mouse.click(box.x + GUTTER + 2500 * pxPerMs, box.y + RULER / 2);
  await page.mouse.click(box.x + GUTTER + 2500 * pxPerMs, box.y + RULER + 1 * ROW_H + ROW_H / 2); // select the scrum (row 2)
  await page.keyboard.press('Alt+s');
  await expect.poll(async () => (await tags(page, eventId)).filter((t) => t.code === 'Scrum').length).toBe(2);
  const scrums = (await tags(page, eventId)).filter((t) => t.code === 'Scrum').sort((a, b) => a.start_ms - b.start_ms);
  expect(scrums[0].end_ms).toBe(scrums[1].start_ms);
  expect(scrums[1].end_ms).toBe(5000);

  // Merge them back with Alt+M after selecting both with Shift+click.
  await page.mouse.click(box.x + GUTTER + 1000 * pxPerMs, box.y + RULER + 1 * ROW_H + ROW_H / 2);
  await page.mouse.click(box.x + GUTTER + 4000 * pxPerMs, box.y + RULER + 1 * ROW_H + ROW_H / 2, { modifiers: ['Shift'] });
  await page.keyboard.press('Alt+m');
  await expect.poll(async () => (await tags(page, eventId)).filter((t) => t.code === 'Scrum').length).toBe(1);
  [scrum] = (await tags(page, eventId)).filter((t) => t.code === 'Scrum');
  expect(scrum.start_ms).toBe(0);
  expect(scrum.end_ms).toBe(5000);

  // Set an outcome on the scrum (selected) and add a note.
  await page.getByTestId('descriptor-outcome-Lost').click();
  await page.getByTestId('tag-note').fill('Wheeled under pressure');
  await page.getByTestId('tag-note').blur();
  await expect.poll(async () => (await tags(page, eventId)).find((t) => t.code === 'Scrum')!.descriptors.outcome).toBe('Lost');

  // Find clips: chips, result count, save as a playlist.
  await page.getByTestId('nav-find-clips').click();
  await expect(page.getByTestId('clip-count')).toContainText('2 clips');
  await page.getByTestId('chip-code-Scrum').click();
  await expect(page.getByTestId('clip-count')).toContainText('1 clip');
  await expect(page.getByTestId('clip-card').first()).toContainText('Scrum · Lost');
  await page.getByTestId('chip-code-Scrum').click();
  await page.getByTestId('chip-outcome-Lost').click();
  await expect(page.getByTestId('clip-count')).toContainText('1 clip');
  await page.getByTestId('chip-outcome-Lost').click();
  await expect(page.getByTestId('clip-count')).toContainText('2 clips');
  await page.getByTestId('save-filter').click();
  await page.getByTestId('save-filter-name').fill('Everything');
  await page.getByTestId('save-filter-confirm').click();
  await expect(page.getByTestId('saved-filters')).toBeVisible();

  await page.getByTestId('add-to-playlist').click();
  await page.getByTestId('new-playlist-name').fill('Demo highlights');
  await page.getByTestId('new-playlist-create').click();
  await expect(page.getByTestId('playlist-title')).toHaveText('Demo highlights');
  await expect(page.getByTestId('playlist-item')).toHaveCount(2);

  // Play through: next and previous, by button and key.
  await page.getByTestId('play-all').click();
  await expect(page.getByTestId('clip-position')).toHaveText('Clip 1 of 2');
  await page.getByTestId('next-clip').click();
  await expect(page.getByTestId('clip-position')).toHaveText('Clip 2 of 2');
  await page.keyboard.press('p');
  await expect(page.getByTestId('clip-position')).toHaveText('Clip 1 of 2');
  await page.getByTestId('rename').click();
  await page.getByTestId('rename-input').fill('Demo highlights v2');
  await page.getByTestId('rename-input').press('Enter');
  await expect(page.getByTestId('playlist-title')).toHaveText('Demo highlights v2');

  // Export the playlist; the worker runs inline in the test API, so it is ready at once.
  await page.getByTestId('export-playlist').click();
  await page.getByTestId('export-confirm').click();
  await expect(page.getByTestId('export-row').first()).toBeVisible();
  await expect(page.getByTestId('export-status').first()).toHaveText('Ready', { timeout: 60_000 });
  const download = page.getByTestId('export-download').first();
  await expect(download).toHaveAttribute('href', /\/media\/exports\//);
  const file = await page.request.get((await download.getAttribute('href'))!);
  expect(file.ok()).toBeTruthy();
  expect(Number(file.headers()['content-length'])).toBeGreaterThan(10_000);

  // Stats: counts per code and a number that opens a playlist.
  await page.getByTestId('nav-stats').click();
  await expect(page.getByTestId('codes-table')).toContainText('Scrum');
  const scrumRow = page.getByTestId('codes-table').locator('tr', { hasText: 'Scrum' });
  await expect(scrumRow).toContainText('0%');
  await scrumRow.getByTestId('stat-number').first().click();
  await expect(page.getByTestId('playlist-title')).toContainText('Scrum');
  await expect(page.getByTestId('playlist-item')).toHaveCount(1);
});

test('a coach sees the simple screens and cannot tag', async ({ page }) => {
  // Make a coach through the API as the admin, then sign in as them.
  await login(page);
  const squads = await (await page.request.get('/api/squads')).json();
  const squadId = squads[0].id as string;
  const csrf = (await page.context().cookies()).find((c) => c.name === 'rugby_csrf')!.value;
  const created = await page.request.post(`/api/squads/${squadId}/members`, {
    headers: { 'X-CSRF-Token': csrf },
    data: { email: 'coach@example.com', role: 'coach', name: 'Coach Casey', password: 'coach-password-123' },
  });
  expect([201, 409]).toContain(created.status());
  await page.getByTestId('user-menu').click();
  await page.getByTestId('logout').click();

  await page.goto('/login');
  await page.getByTestId('login-email').fill('coach@example.com');
  await page.getByTestId('login-password').fill('coach-password-123');
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('nav-find-clips')).toBeVisible();
  await expect(page.getByTestId('nav-templates')).toHaveCount(0);
  await page.getByTestId('event-card').first().click();
  await expect(page.getByTestId('tag-match')).toHaveCount(0);
  await page.getByTestId('nav-find-clips').click();
  await expect(page.getByTestId('chip-code-Scrum')).toBeVisible();
  await page.getByTestId('nav-playlists').click();
  await expect(page.getByTestId('new-playlist')).toBeVisible();
});
