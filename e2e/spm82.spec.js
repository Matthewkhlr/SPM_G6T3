import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { completeRequestPayload } from './support/api-data.js'
import { createDraftEvent, eventApi, submitEvent } from './support/event.js'

test.describe('SPM-82 Submit an event request for review', () => {
  test('TC-SPM82-AC01 submission lists every missing required field and is blocked', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.locator('.nav-item').getByText('New Request', { exact: true }).click()
    await page.getByTestId('event-submit').click()
    const errors = page.getByTestId('submit-missing-fields')
    await expect(errors).toBeVisible()
    for (const label of [/name/i, /category/i, /purpose/i, /date|start|end/i, /attendance/i, /registration/i]) {
      await expect(errors).toContainText(label)
    }
  })

  test('TC-SPM82-AC02 a complete draft becomes Submitted with a timestamp and appears in the review queue', async () => {
    const draft = await eventApi('POST', '', 'EO-01', completeRequestPayload('AUTO-SPM82-submit'))
    const submitted = await submitEvent(draft.body.eventId)
    expect(submitted.status).toBe(200)
    expect(submitted.body.status).toMatch(/submitted/i)
    expect(submitted.body.submittedAt).toBeTruthy()
    const queue = await eventApi('GET', '/queue', 'EC-01')
    expect((queue.body || []).map((row) => row.eventId)).toContain(draft.body.eventId)
  })

  test('TC-SPM82-AC03 the organiser sees immediate confirmation naming the event and its reference', async ({
    page,
  }) => {
    const draft = await eventApi('POST', '', 'EO-01', completeRequestPayload('AUTO-SPM82-confirm'))
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${draft.body.eventId}`)
    await page.getByTestId('event-submit').click()
    const confirm = page.getByTestId('submit-confirmation')
    await expect(confirm).toBeVisible()
    await expect(confirm).toContainText('AUTO-SPM82-confirm')
    await expect(confirm).toContainText(draft.body.eventId)
  })

  test('TC-SPM82-AC04 a submitted event is not directly editable; the screen offers the change-request route', async ({
    page,
  }) => {
    const event = await createDraftEvent('EO-01', 'AUTO-SPM82-locked')
    await submitEvent(event.eventId)
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await expect(page.getByTestId('event-name-input')).toHaveCount(0)
    await expect(page.getByTestId('raise-change-request')).toBeVisible()
  })

  test('TC-SPM82-AC05 submitting an already submitted event is refused and the status is unchanged', async () => {
    const event = await createDraftEvent('EO-01', 'AUTO-SPM82-twice')
    const first = await submitEvent(event.eventId)
    const again = await submitEvent(event.eventId)
    expect([400, 409]).toContain(again.status)
    const stored = await eventApi('GET', `/${event.eventId}`, 'EO-01')
    expect(stored.body.status).toMatch(/submitted/i)
    expect(stored.body.submittedAt).toBe(first.body.submittedAt)
  })

  test('TC-SPM82-AC06 submitting notifies ConnectSphere that a new request has arrived', async () => {
    const event = await createDraftEvent('EO-01', 'AUTO-SPM82-notify')
    await submitEvent(event.eventId)
    const queue = await eventApi('GET', '/queue', 'EC-01')
    expect((queue.body || []).map((row) => row.eventId)).toContain(event.eventId)
  })

  test('TC-SPM82-AC07 a request whose proposed date is soon can be submitted with no minimum notice', async () => {
    const start = new Date(Date.now() + 3 * 60 * 60 * 1000)
    const draft = await eventApi(
      'POST',
      '',
      'EO-01',
      completeRequestPayload('AUTO-SPM82-soon', {
        proposedStartAt: start.toISOString(),
        proposedEndAt: new Date(start.getTime() + 3600000).toISOString(),
      }),
    )
    const submitted = await submitEvent(draft.body.eventId)
    expect(submitted.status).toBe(200)
  })
})
