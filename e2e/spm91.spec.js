import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { eventApi } from './support/event.js'

test.describe('SPM-91 Browse events open for registration', () => {
  test('TC-SPM91-AC01 an attendee sees confirmed, registration-enabled events that are within their period', async () => {
    const list = await eventApi('GET', '/open-for-registration', 'ATT-01')
    expect(list.status).toBe(200)
    const ids = (list.body || []).map((row) => row.eventId)
    expect(ids).toContain('e1')
    expect(ids).not.toContain('e3')
    expect(ids).not.toContain('e4')
    expect(ids).not.toContain('e6')
    expect(ids).not.toContain('e8')
  })

  test('TC-SPM91-AC02 each event shows name, category, date, start and end time, venue name and location, and remaining places', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    await page.locator('.nav-item').getByText('Browse Events', { exact: true }).click()
    const card = page.getByTestId('browse-event-e1')
    await expect(card).toBeVisible()
    await expect(card).toContainText('AI in Events Summit')
    await expect(card.getByTestId('browse-category')).toBeVisible()
    await expect(card.getByTestId('browse-date')).toBeVisible()
    await expect(card.getByTestId('browse-start')).toBeVisible()
    await expect(card.getByTestId('browse-end')).toBeVisible()
    await expect(card).toContainText('Marina Hall A')
    await expect(card).toContainText('HarbourFront Centre')
    await expect(card.getByTestId('browse-remaining')).toBeVisible()
  })

  test('TC-SPM91-AC03 opening an event shows description, accessibility, registration close, and remaining places', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    await page.goto('/app/browse/e1')
    await expect(page.getByTestId('browse-description')).toBeVisible()
    await expect(page.getByTestId('browse-accessibility')).toContainText(/wheelchair|access/i)
    await expect(page.getByTestId('browse-closes-at')).toBeVisible()
    await expect(page.getByTestId('browse-remaining')).toBeVisible()
  })

  test('TC-SPM91-AC04 full events are shown, marked full, with registration unavailable', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    await page.locator('.nav-item').getByText('Browse Events', { exact: true }).click()
    const full = page.getByTestId('browse-event-e2')
    await expect(full).toBeVisible()
    await expect(full).toHaveAttribute('data-full', 'true')
    await expect(full).toContainText(/full/i)
    await expect(full.getByTestId('event-register')).toHaveCount(0)
  })

  test('TC-SPM91-AC05 draft, submitted, planning, completed, cancelled, or rejected events never appear, and a direct request returns no event data', async () => {
    const list = await eventApi('GET', '/open-for-registration', 'ATT-01')
    const ids = (list.body || []).map((row) => row.eventId)
    expect(ids).not.toContain('e3')
    expect(ids).not.toContain('e6')
    expect(ids).not.toContain('e8')
    for (const id of ['e3', 'e6', 'e8']) {
      const hidden = await eventApi('GET', `/open-for-registration/${id}`, 'ATT-01')
      expect([403, 404]).toContain(hidden.status)
    }
  })

  test('TC-SPM91-AC06 events whose registration period has not opened or has closed do not appear', async () => {
    const list = await eventApi('GET', '/open-for-registration', 'ATT-01')
    const ids = (list.body || []).map((row) => row.eventId)
    expect(ids).not.toContain('e4')
  })

  test('TC-SPM91-AC07 attendees can search by name and filter by category and date range', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    await page.locator('.nav-item').getByText('Browse Events', { exact: true }).click()
    await page.getByTestId('browse-search').fill('AI in Events')
    await expect(page.getByTestId('browse-event-e1')).toBeVisible()
    await page.getByTestId('browse-filter-category').selectOption(/conference/i)
    await page.getByTestId('browse-filter-from').fill(new Date().toISOString().slice(0, 10))
  })

  test('TC-SPM91-AC08 no coordinator name, internal note, client organisation, or other attendee identity is shown', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    await page.locator('.nav-item').getByText('Browse Events', { exact: true }).click()
    await expect(page.getByTestId('browse-event-e1')).toBeVisible()
    const body = await page.locator('body').innerText()
    expect(body).not.toMatch(/Ben Lee|Apex Partners|Demo Attendee|one@example\.com|internal note/i)
  })

  test('TC-SPM91-AC09 when no events are open, an empty state says so rather than an error', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    await page.route('**/open-for-registration', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
    })
    await page.locator('.nav-item').getByText('Browse Events', { exact: true }).click()
    const empty = page.getByTestId('browse-empty')
    await expect(empty).toBeVisible()
    await expect(empty).toContainText(/no events|none open/i)
    await expect(page.getByTestId('browse-error')).toHaveCount(0)
  })
})
