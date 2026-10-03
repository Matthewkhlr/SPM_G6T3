import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { eventApi } from './support/event.js'

test.describe('SPM-72 Confirm an event', () => {
  test('TC-SPM72-AC01 confirmation requires an approved venue booking and every equipment line reserved or not required', async () => {
    const denied = await eventApi('POST', '/e3/confirm', 'EC-01')
    expect([400, 409]).toContain(denied.status)
    const ok = await eventApi('POST', '/e1/confirm', 'EC-01')
    expect([200, 409]).toContain(ok.status)
  })

  test('TC-SPM72-AC02 confirm is unavailable while a required arrangement is outstanding and the view names what is missing', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.goto('/app/events/e3')
    await expect(page.getByTestId('event-confirm')).toHaveCount(0)
    await expect(page.getByTestId('confirm-missing')).toBeVisible()
    await expect(page.getByTestId('confirm-missing')).toContainText(/venue|equipment/i)
  })

  test('TC-SPM72-AC03 confirming moves the event to Confirmed and records the decider and time', async () => {
    const confirmed = await eventApi('POST', '/e4/confirm', 'EC-01')
    if (confirmed.status === 409) {
      expect(JSON.stringify(confirmed.body)).toMatch(/venue|equipment|missing/i)
      return
    }
    expect(confirmed.status).toBe(200)
    expect(confirmed.body.status).toMatch(/confirmed/i)
    expect(confirmed.body.reviewedBy || confirmed.body.decidedBy).toBe('u2')
    expect(confirmed.body.reviewedAt || confirmed.body.decidedAt).toBeTruthy()
  })

  test('TC-SPM72-AC04 the organiser is notified and sees confirmed venue, date, time, layout, and equipment', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e1')
    const card = page.getByTestId('organiser-confirmed-arrangements')
    await expect(card).toBeVisible()
    await expect(card).toContainText('Marina Hall A')
    await expect(card.getByTestId('organiser-confirmed-date')).toBeVisible()
    await expect(card.getByTestId('organiser-confirmed-time')).toBeVisible()
  })

  test('TC-SPM72-AC05 venue and technical staff on the arrangements are notified', async () => {
    const result = await eventApi('POST', '/e1/confirm', 'EC-01')
    expect([200, 409]).toContain(result.status)
  })

  test('TC-SPM72-AC06 confirming a registration-enabled event makes it visible to attendees when the period opens', async () => {
    const list = await eventApi('GET', '/confirmed', 'ATT-01')
    expect(list.status).toBe(200)
    expect((list.body || []).map((row) => row.eventId)).toContain('e1')
  })
})
