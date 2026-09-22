import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'

test.describe('SPM-46 future UI acceptance contracts', () => {
  test('TC-SPM46-AC01 assigned coordinator has action controls on event details', async ({
    page,
  }) => {
    test.skip(true, 'Event details page is not implemented; remove when SPM-46 AC1 ships.')

    await login(page, account('EC-01'))
    await page.goto('/app/events/e1')
    await expect(page.getByRole('button', { name: 'Edit planning' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Submit venue booking' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Request equipment' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Confirm arrangements' })).toBeVisible()
  })

  test('TC-SPM46-AC02 unassigned staff see event details read-only', async ({ page }) => {
    test.skip(true, 'Event details page is not implemented; remove when SPM-46 AC2 ships.')

    await login(page, account('VS-01'))
    await page.goto('/app/events/e1')
    await expect(page.getByTestId('event-name')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Edit planning' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Submit venue booking' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Request equipment' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Confirm arrangements' })).toHaveCount(0)
  })

  test('TC-SPM46-AC03 reassignment swaps action controls without sign-out', async ({ page }) => {
    test.skip(true, 'Event details page is not implemented; remove when SPM-46 AC3 ships.')

    await login(page, account('EC-01'))
    await page.goto('/app/events/e3')
    await expect(page.getByRole('button', { name: 'Edit planning' })).toBeVisible()
    await page.getByRole('button', { name: 'Reassign coordinator' }).click()
    await page.getByLabel('Coordinator').selectOption('u6')
    await page.getByRole('button', { name: 'Confirm assignment' }).click()
    await expect(page.getByRole('button', { name: 'Edit planning' })).toHaveCount(0)
  })
})
