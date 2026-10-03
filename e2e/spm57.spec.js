import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'

test.describe('SPM-57 Venue Staff dashboard', () => {
  test('TC-SPM57-AC01 pending booking requests show event, venue, and datetime', async ({
    page,
  }) => {
    await login(page, account('VS-01'))
    await expect(page.getByTestId('venue-section-pending')).toBeVisible()
    const item = page.getByTestId('venue-pending-vb-pending')
    await expect(item).toBeVisible()
    await expect(item).toContainText('AI in Events Summit')
    await expect(item).toContainText('Marina Hall A')
    await expect(item.getByTestId('venue-pending-vb-pending-datetime')).toBeVisible()
  })

  test('TC-SPM57-AC02 bookings flagged for re-verification are shown', async ({ page }) => {
    await login(page, account('VS-01'))
    await expect(page.getByTestId('venue-section-reverification')).toBeVisible()
    const item = page.getByTestId('venue-reverification-vb-reverify')
    await expect(item).toBeVisible()
    await expect(item).toContainText('Venue Ops Workshop')
  })

  test('TC-SPM57-AC03 confirmed bookings in the next few days are shown', async ({ page }) => {
    await login(page, account('VS-01'))
    await expect(page.getByTestId('venue-section-upcoming')).toBeVisible()
    const item = page.getByTestId('venue-upcoming-vb-soon')
    await expect(item).toBeVisible()
    await expect(item).toContainText('AI in Events Summit')
    await expect(item).toContainText('Marina Hall A')
  })

  test('TC-SPM57-AC04 each item opens the work screen', async ({ page }) => {
    await login(page, account('VS-01'))

    await expect(page.getByTestId('venue-pending-vb-pending')).toBeVisible()
    await page.getByTestId('venue-pending-vb-pending').click()
    await expect(page).toHaveURL(/booking|venue|vb-pending|request/i)
    await page.goto('/app')

    await page.getByTestId('venue-reverification-vb-reverify').click()
    await expect(page).toHaveURL(/booking|venue|vb-reverify|re-?verif/i)
    await page.goto('/app')

    await page.getByTestId('venue-upcoming-vb-soon').click()
    await expect(page).toHaveURL(/booking|venue|calendar|vb-soon/i)
  })

  test('TC-SPM57-AC05 lists obey the same access rules as the work screens', async ({ page }) => {
    await login(page, account('VS-01'))
    await expect(page.getByTestId('venue-pending-vb-pending')).toBeVisible()
    await page.getByRole('button', { name: 'Log out' }).click()
    await login(page, account('EO-01'))
    await expect(page.getByTestId('venue-pending-vb-pending')).toHaveCount(0)
    await expect(page.getByTestId('venue-section-pending')).toHaveCount(0)
  })

  test('TC-SPM57-AC06 each section has an empty state', async ({ page }) => {
    await login(page, account('VS-02'))
    await expect(page.getByTestId('venue-pending-empty')).toBeVisible()
    await expect(page.getByTestId('venue-reverification-empty')).toBeVisible()
    await expect(page.getByTestId('venue-upcoming-empty')).toBeVisible()
  })
})
