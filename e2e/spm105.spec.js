import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { registrationApi } from './support/registration.js'

test.describe('SPM-105 View who has registered for my event', () => {
  test('TC-SPM105-AC01 the organiser and assigned coordinator can see the registration list for that event only', async () => {
    const organiser = await registrationApi('GET', '/registrations?eventId=e1', 'EO-01')
    expect(organiser.status).toBe(200)
    expect(JSON.stringify(organiser.body)).toMatch(/Amy Wong/)
    expect(JSON.stringify(organiser.body)).not.toMatch(/r-att-e2/)
    const coord = await registrationApi('GET', '/registrations?eventId=e1', 'EC-01')
    expect(coord.status).toBe(200)
  })

  test('TC-SPM105-AC02 the list shows name, supplied information, registered time, and registered or withdrawn', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e1/registrations')
    const row = page.getByTestId('registration-r-att-e1')
    await expect(row).toBeVisible()
    await expect(row).toContainText('Amy Wong')
    await expect(row.getByTestId('registration-created-at')).toBeVisible()
    await expect(row).toContainText(/registered/i)
  })

  test('TC-SPM105-AC03 a summary shows capacity, registered, withdrawn, and remaining, and withdrawn rows can be filtered out', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e1/registrations')
    const summary = page.getByTestId('registration-summary')
    await expect(summary.getByTestId('summary-capacity')).toContainText('3')
    await expect(summary.getByTestId('summary-registered')).toBeVisible()
    await expect(summary.getByTestId('summary-withdrawn')).toBeVisible()
    await expect(summary.getByTestId('summary-remaining')).toBeVisible()
    await page.getByTestId('filter-hide-withdrawn').click()
    await expect(page.locator('[data-registration-status="withdrawn"]')).toHaveCount(0)
  })

  test('TC-SPM105-AC04 no other organiser, coordinator, or role can read the list, enforced on the server', async () => {
    for (const id of ['EO-02', 'EC-02', 'VS-01', 'ATT-01']) {
      const denied = await registrationApi('GET', '/registrations?eventId=e1', id)
      expect([403, 404], id).toContain(denied.status)
    }
  })

  test('TC-SPM105-AC05 when registration is not enabled, no registration list is offered', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e3')
    await expect(page.getByTestId('event-registrations')).toHaveCount(0)
  })

  test('TC-SPM105-AC06 when nobody has registered yet, an empty state shows capacity and the registration period', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e4/registrations')
    const empty = page.getByTestId('registrations-empty')
    await expect(empty).toBeVisible()
    await expect(empty).toContainText(/50|capacity/i)
    await expect(empty).toContainText(/open|period|closes/i)
  })
})
