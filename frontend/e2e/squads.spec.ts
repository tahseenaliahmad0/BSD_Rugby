import { expect, test, type Page } from '@playwright/test';

const ADMIN = { email: 'admin@example.com', password: 'admin-password-123' };

async function login(page: Page) {
  await page.goto('/login');
  await page.getByTestId('login-email').fill(ADMIN.email);
  await page.getByTestId('login-password').fill(ADMIN.password);
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('squad-switcher')).toBeVisible();
}

test('an administrator creates a squad from the menu and lands in it', async ({ page }) => {
  await login(page);
  const name = `Women's XV ${Date.now()}`;

  await page.getByTestId('user-menu').click();
  await page.getByTestId('new-squad').click();
  await page.getByTestId('new-squad-name').fill(name);
  await page.getByTestId('new-squad-variant').getByText('Sevens').click();
  await page.getByTestId('new-squad-submit').click();

  await expect(page).toHaveURL(/\/squads\/[0-9a-f-]{36}$/);
  await expect(page.getByTestId('squad-switcher')).toHaveValue(name);

  // The new squad came with the default sevens template.
  await page.getByRole('link', { name: 'Templates' }).click();
  await expect(page.getByText(/sevens/i).first()).toBeVisible();

  // A second squad with the same name is refused with a readable message.
  await page.getByTestId('user-menu').click();
  await page.getByTestId('new-squad').click();
  await page.getByTestId('new-squad-name').fill(name);
  await page.getByTestId('new-squad-submit').click();
  await expect(page.getByText('A squad with that name already exists.')).toBeVisible();
});
