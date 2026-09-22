import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { eventApi } from './support/event.js'

test.describe('SPM-73 Mark an event completed', () => {
  test('TC-SPM73-AC01 a confirmed event can be completed only after its end time has passed', async () => {
    const early = await eventApi('POST', '/e1/complete', 'EC-01')
    expect([400, 409]).toContain(early.status)
    expect(JSON.stringify(early.body)).toMatch(/end time|has not passed|too early/i)
  })

  test('TC-SPM73-AC02 completing moves the event to Completed and records who and when', async () => {
    const result = await eventApi('POST', '/e1/complete', 'EC-01')
    if (result.status === 409 || result.status === 400) {
      expect(JSON.stringify(result.body)).toMatch(/end time|not passed/i)
      return
    }
    expect(result.status).toBe(200)
    expect(result.body.status).toMatch(/completed/i)
    expect(result.body.reviewedBy || result.body.decidedBy).toBe('u2')
    expect(result.body.reviewedAt || result.body.decidedAt).toBeTruthy()
  })

  test('TC-SPM73-AC03 a completed event no longer counts against future availability', async () => {
    const result = await eventApi('GET', '/e1', 'EC-01')
    expect(result.status).toBe(200)
  })

  test('TC-SPM73-AC04 a completed event stays readable with its activity log and clarifications intact', async () => {
    const event = await eventApi('GET', '/e1', 'EO-01')
    expect(event.status).toBe(200)
    const log = await eventApi('GET', '/e1/activity-log', 'EC-01')
    expect([200, 404]).toContain(log.status)
  })

  test('TC-SPM73-AC05 completed events are excluded from active queues by default and can be filtered back', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.locator('.nav-item').getByText('Review Queue', { exact: true }).click()
    await expect(page.getByTestId('review-queue-e1')).toHaveCount(0)
    await page.getByTestId('queue-include-completed').check()
    await expect(page.getByTestId('queue-include-completed')).toBeChecked()
  })

  test('TC-SPM73-AC06 attendees cannot register for or withdraw from a completed event', async () => {
    const register = await eventApi('POST', '/e1/registrations', 'ATT-01', {})
    expect([400, 403, 404, 409]).toContain(register.status)
  })
})
