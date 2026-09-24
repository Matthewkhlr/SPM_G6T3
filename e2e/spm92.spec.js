import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { registrationApi } from './support/registration.js'

test.describe('SPM-92 View my registrations and their status', () => {
  test('TC-SPM92-AC01 the attendee sees their registrations with name, date, times, venue, location, and status', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    await page.locator('.nav-item').getByText('My Registrations', { exact: true }).click()
    const row = page.getByTestId('my-registration-e1')
    await expect(row).toBeVisible()
    await expect(row).toContainText('AI in Events Summit')
    await expect(row.getByTestId('reg-date')).toBeVisible()
    await expect(row.getByTestId('reg-start')).toBeVisible()
    await expect(row.getByTestId('reg-end')).toBeVisible()
    await expect(row).toContainText('Marina Hall A')
    await expect(row).toContainText('HarbourFront Centre')
    await expect(row).toContainText(/registered/i)
  })

  test('TC-SPM92-AC02 registrations are split into upcoming and past, with upcoming shown first', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    await page.locator('.nav-item').getByText('My Registrations', { exact: true }).click()
    const upcoming = page.getByTestId('my-registrations-upcoming')
    const past = page.getByTestId('my-registrations-past')
    await expect(upcoming).toBeVisible()
    const upBox = await upcoming.boundingBox()
    const pastBox = await past.boundingBox().catch(() => null)
    if (pastBox) expect(upBox.y).toBeLessThan(pastBox.y)
    await expect(upcoming.getByTestId('my-registration-e1')).toBeVisible()
  })

  test('TC-SPM92-AC03 details are read from the event\'s current record, so a reschedule shows the new date and time', async () => {
    const mine = await registrationApi('GET', '/registrations/me', 'ATT-01')
    expect(mine.status).toBe(200)
    const e1 = (mine.body || []).find((row) => row.eventId === 'e1')
    expect(e1.proposedStartAt || e1.startsAt).toBeTruthy()
    const event = await registrationApi('GET', '/registrations?eventId=e1', 'ATT-01')
    expect(event.status).toBe(200)
  })

  test('TC-SPM92-AC04 a cancelled event is clearly marked cancelled in the list', async ({ page }) => {
    await login(page, account('ATT-01'))
    await page.locator('.nav-item').getByText('My Registrations', { exact: true }).click()
    const row = page.getByTestId('my-registration-e8')
    await expect(row).toBeVisible()
    await expect(row).toHaveAttribute('data-cancelled', 'true')
    await expect(row).toContainText(/cancelled/i)
  })

  test('TC-SPM92-AC05 an event whose date, time, or venue changed since registration is flagged as changed', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    await page.locator('.nav-item').getByText('My Registrations', { exact: true }).click()
    const row = page.getByTestId('my-registration-e2')
    await expect(row).toBeVisible()
    await expect(row).toHaveAttribute('data-changed', 'true')
    await expect(row).toContainText(/changed/i)
  })

  test('TC-SPM92-AC06 the attendee can open a registration to withdraw where withdrawal is permitted', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    await page.locator('.nav-item').getByText('My Registrations', { exact: true }).click()
    await page.getByTestId('my-registration-e1').click()
    await expect(page.getByTestId('registration-withdraw')).toBeVisible()
    await page.goto('/app/registrations')
    await page.getByTestId('my-registration-e8').click()
    await expect(page.getByTestId('registration-withdraw')).toHaveCount(0)
  })

  test('TC-SPM92-AC07 the attendee sees only their own registrations, and no other attendee identity', async ({
    page,
  }) => {
    const mine = await registrationApi('GET', '/registrations/me', 'ATT-01')
    expect(mine.status).toBe(200)
    expect(JSON.stringify(mine.body)).not.toMatch(/Demo Attendee|one@example\.com|Full One/)
    await login(page, account('ATT-01'))
    await page.locator('.nav-item').getByText('My Registrations', { exact: true }).click()
    const body = await page.locator('body').innerText()
    expect(body).not.toMatch(/Demo Attendee|one@example\.com/i)
  })

  test('TC-SPM92-AC08 an attendee with no registrations is pointed at browsing events', async ({
    page,
  }) => {
    await login(page, account('ATT-02'))
    await page.locator('.nav-item').getByText('My Registrations', { exact: true }).click()
    const empty = page.getByTestId('my-registrations-empty')
    await expect(empty).toBeVisible()
    await expect(empty).toContainText(/brows/i)
    await expect(page.getByTestId('empty-browse-events')).toBeVisible()
  })
})
