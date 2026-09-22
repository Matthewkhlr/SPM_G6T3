import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { assignCoordinator, createSubmittedEvent, eventApi } from './support/event.js'

async function underReviewEvent() {
  const event = await createSubmittedEvent('EO-01', `AUTO-SPM69-${Date.now()}`)
  await assignCoordinator(event.eventId, 'u2', 'EC-01')
  return event.eventId
}

test.describe('SPM-69 Approve a submitted request so planning can begin', () => {
  test('TC-SPM69-AC01 the assigned coordinator can approve an Under Review event with an optional note', async () => {
    const eventId = await underReviewEvent()
    const approved = await eventApi('POST', `/${eventId}/approve`, 'EC-01', {
      note: 'Ready for planning',
    })
    expect(approved.status).toBe(200)
    expect(approved.body.status).toMatch(/planning/i)
    expect(approved.body.decisionNote || approved.body.note).toMatch(/planning/)
  })

  test('TC-SPM69-AC02 approving moves the event to Planning and records the decider and time', async () => {
    const eventId = await underReviewEvent()
    const approved = await eventApi('POST', `/${eventId}/approve`, 'EC-01', {})
    expect(approved.status).toBe(200)
    expect(approved.body.status).toMatch(/planning/i)
    expect(approved.body.reviewedBy || approved.body.decidedBy).toBe('u2')
    expect(approved.body.reviewedAt || approved.body.decidedAt).toBeTruthy()
  })

  test('TC-SPM69-AC03 the organiser is notified and can see the outcome and note', async ({ page }) => {
    const eventId = await underReviewEvent()
    await eventApi('POST', `/${eventId}/approve`, 'EC-01', { note: 'Taken on' })
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${eventId}`)
    await expect(page.getByTestId('organiser-decision')).toContainText(/approved|planning|taken on/i)
  })

  test('TC-SPM69-AC04 approving with open clarifications warns and requires confirm', async ({
    page,
  }) => {
    const eventId = await underReviewEvent()
    await eventApi('POST', `/${eventId}/clarifications`, 'EC-01', {
      message: 'Still open',
    })
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${eventId}`)
    await page.getByTestId('event-approve').click()
    await expect(page.getByTestId('approve-open-clarifications-warning')).toBeVisible()
    await page.getByTestId('approve-confirm-anyway').click()
    const stored = await eventApi('GET', `/${eventId}`, 'EC-01')
    expect(stored.body.status).toMatch(/planning/i)
  })

  test('TC-SPM69-AC05 approval is unavailable for an unassigned submitted event', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.goto('/app/events/e6')
    await expect(page.getByTestId('event-approve')).toHaveCount(0)
    const denied = await eventApi('POST', '/e6/approve', 'EC-01', {})
    expect([400, 403, 409]).toContain(denied.status)
  })

  test('TC-SPM69-AC06 approval does not reserve venue or equipment; arrangements stay outstanding', async () => {
    const eventId = await underReviewEvent()
    const approved = await eventApi('POST', `/${eventId}/approve`, 'EC-01', {})
    expect(approved.status).toBe(200)
    const readiness = await eventApi('GET', `/${eventId}/readiness`, 'EC-01')
    expect(readiness.status).toBe(200)
    const outstanding = (readiness.body || []).filter((row) =>
      /outstanding|not required|pending/i.test(row.status),
    )
    expect(outstanding.length).toBeGreaterThan(0)
  })
})
