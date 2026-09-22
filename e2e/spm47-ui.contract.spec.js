import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'

test.describe('SPM-47 future UI acceptance contracts', () => {
  test('TC-SPM47-AC01 My Events and Drafts stay inside the organiser organisation', async ({
    page,
  }) => {
    test.skip(true, 'My Events / Drafts screens are not implemented; remove when SPM-47 AC1 ships.')

    await login(page, account('EO-01'))
    await page.locator('.nav-item').getByText('My Events', { exact: true }).click()
    await expect(page.getByText('AI in Events Summit')).toBeVisible()
    await expect(page.getByText('Beacon Q4 Showcase')).toHaveCount(0)

    await page.locator('.nav-item').getByText('Drafts', { exact: true }).click()
    await expect(page.getByText('Partner Networking Night')).toBeVisible()
    await expect(page.getByText('Beacon Q4 Showcase')).toHaveCount(0)
  })

  test('TC-SPM47-AC02 foreign event URL is rejected', async ({ page }) => {
    test.skip(true, 'Event details page is not implemented; remove when SPM-47 AC2 ships.')

    await login(page, account('EO-01'))
    await page.goto('/app/events/e5')
    await expect(page.getByText('Beacon Q4 Showcase')).toHaveCount(0)
    await expect(page.getByText(/not found|forbidden|do not have access/i)).toBeVisible()
  })

  test('TC-SPM47-AC03 attendee browse hides drafts and other registrations', async ({ page }) => {
    test.skip(true, 'Attendee browse and registration screens are not implemented; remove when SPM-47 AC3 ships.')

    await login(page, account('ATT-01'))
    await page.locator('.nav-item').getByText('Browse Events', { exact: true }).click()
    await expect(page.getByText('AI in Events Summit')).toBeVisible()
    await expect(page.getByText('Partner Networking Night')).toHaveCount(0)
    await expect(page.getByText(/coordinator|staff note|clarification/i)).toHaveCount(0)

    await page.locator('.nav-item').getByText('My Registrations', { exact: true }).click()
    await expect(page.getByText('Demo Attendee')).toHaveCount(0)
    await expect(page.getByText('one@example.com')).toHaveCount(0)
  })
})
