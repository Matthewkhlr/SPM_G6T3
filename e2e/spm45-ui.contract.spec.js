import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'

test.describe('SPM-45 future UI acceptance contracts', () => {
  test('TC-SPM45-AC01 Venue Staff manages booking requests', async ({ page }) => {
    test.skip(
      true,
      'Booking Requests UI and booking-list endpoint are not implemented; remove when SPM-45 AC1 ships.',
    )

    await login(page, account('VS-01'))
    await page.locator('.nav-item').getByText('Booking Requests', { exact: true }).click()
    await expect(page.getByTestId('venue-booking-request')).toHaveCount(2)
    await page.getByTestId('venue-booking-request').first().getByRole('button', {
      name: 'Approve',
    }).click()
    await expect(page.getByText('Booking approved')).toBeVisible()
  })

  test('TC-SPM45-AC02 Technical Support reviews and reserves equipment', async ({ page }) => {
    test.skip(
      true,
      'Reservations UI and equipment-request listing are not implemented; remove when SPM-45 AC2 ships.',
    )

    await login(page, account('TS-01'))
    await page.locator('.nav-item').getByText('Reservations', { exact: true }).click()
    const request = page.getByTestId('equipment-request').first()
    await expect(request.getByTestId('technical-requirements')).toBeVisible()
    await request.getByRole('button', { name: 'Approve' }).click()
    await request.getByRole('button', { name: 'Reserve' }).click()
    await expect(request.getByText('Reserved')).toBeVisible()
  })

  test('TC-SPM45-AC03 Coordinator submits requests and assigns a coordinator', async ({
    page,
  }) => {
    test.skip(
      true,
      'Coordinator assignment and venue/equipment request UI are not implemented; remove when SPM-45 AC3 ships.',
    )

    await login(page, account('EC-01'))
    await page.locator('.nav-item').getByText('Assigned Events', { exact: true }).click()
    await page.getByTestId('event-e1').getByRole('button', { name: 'Assign coordinator' }).click()
    await page.getByLabel('Coordinator').selectOption('u2')
    await page.getByRole('button', { name: 'Confirm assignment' }).click()
    await expect(page.getByText('Coordinator assigned')).toBeVisible()

    await page.locator('.nav-item').getByText('Venue Requests', { exact: true }).click()
    await expect(page.getByRole('button', { name: 'New venue request' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'New equipment request' })).toBeVisible()
    await expect(page.getByRole('button', { name: /approve|reject/i })).toHaveCount(0)
  })

  test('TC-SPM45-AC04 role-inappropriate administrative controls stay hidden', async ({ page }) => {
    test.skip(
      true,
      'Role-specific administrative routes are not implemented; API-level 403 coverage is active.',
    )

    await login(page, account('VS-01'))
    await expect(page.locator('.nav-item').getByText('Reservations', { exact: true })).toHaveCount(0)
    await expect(
      page.locator('.nav-item').getByText('Assigned Events', { exact: true }),
    ).toHaveCount(0)
  })
})
