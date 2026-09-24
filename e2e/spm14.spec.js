import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { completeRequestPayload } from './support/api-data.js'
import { createDraftEvent, eventApi, submitEvent } from './support/event.js'

test.describe('SPM-14 Establish event with ConnectSphere', () => {
  test('TC-SPM14-AC01 submission lists every missing required field and is blocked', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.locator('.nav-item').getByText('New Request', { exact: true }).click()
    await page.getByTestId('event-submit').click()
    const errors = page.getByTestId('submit-missing-fields')
    await expect(errors).toBeVisible()
    await expect(errors).toContainText(/name/i)
    await expect(errors).toContainText(/category/i)
    await expect(errors).toContainText(/purpose/i)
    await expect(errors).toContainText(/date|start|end/i)
    await expect(errors).toContainText(/attendance/i)
    await expect(errors).toContainText(/registration/i)
    const incomplete = await submitEvent('missing-required', 'EO-01')
    expect([400, 404, 422]).toContain(incomplete.status)
  })

  test('TC-SPM14-AC02 a complete draft becomes Submitted with a timestamp and appears in the review queue', async () => {
    const draft = await eventApi('POST', '', 'EO-01', completeRequestPayload('AUTO-SPM14-submit'))
    expect(draft.status).toBe(201)
    const submitted = await submitEvent(draft.body.eventId)
    expect(submitted.status).toBe(200)
    expect(submitted.body.status).toMatch(/submitted/i)
    expect(submitted.body.submittedAt).toBeTruthy()
    const queue = await eventApi('GET', '/queue', 'EC-01')
    expect((queue.body || []).map((row) => row.eventId)).toContain(draft.body.eventId)
  })

  test('TC-SPM14-AC03 the organiser sees immediate confirmation naming the event and its reference', async ({
    page,
  }) => {
    const draft = await eventApi('POST', '', 'EO-01', completeRequestPayload('AUTO-SPM14-confirm'))
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${draft.body.eventId}`)
    await page.getByTestId('event-submit').click()
    const confirm = page.getByTestId('submit-confirmation')
    await expect(confirm).toBeVisible()
    await expect(confirm).toContainText('AUTO-SPM14-confirm')
    await expect(confirm).toContainText(draft.body.eventId)
  })

  test('TC-SPM14-AC04 a submitted event is not directly editable; the screen offers the change-request route', async ({
    page,
  }) => {
    const event = await createDraftEvent('EO-01', 'AUTO-SPM14-locked')
    await submitEvent(event.eventId)
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await expect(page.getByTestId('event-name-input')).toHaveCount(0)
    await expect(page.getByTestId('raise-change-request')).toBeVisible()
    const patched = await eventApi('PATCH', `/${event.eventId}`, 'EO-01', { eventName: 'nope' })
    expect([403, 409]).toContain(patched.status)
  })

  test('TC-SPM14-AC05 submitting an already submitted event is refused and the status is unchanged', async () => {
    const event = await createDraftEvent('EO-01', 'AUTO-SPM14-twice')
    const first = await submitEvent(event.eventId)
    expect(first.status).toBe(200)
    const again = await submitEvent(event.eventId)
    expect([400, 409]).toContain(again.status)
    const stored = await eventApi('GET', `/${event.eventId}`, 'EO-01')
    expect(stored.body.status).toMatch(/submitted/i)
    expect(stored.body.submittedAt).toBe(first.body.submittedAt)
  })

  test('TC-SPM14-AC06 submitting notifies ConnectSphere that a new request has arrived', async () => {
    const event = await createDraftEvent('EO-01', 'AUTO-SPM14-notify')
    const submitted = await submitEvent(event.eventId)
    expect(submitted.status).toBe(200)
    const queue = await eventApi('GET', '/queue', 'EC-01')
    expect((queue.body || []).map((row) => row.eventId)).toContain(event.eventId)
  })

  test('TC-SPM14-AC07 a request whose proposed date is soon can be submitted with no minimum notice', async () => {
    const start = new Date(Date.now() + 2 * 60 * 60 * 1000)
    const end = new Date(start.getTime() + 60 * 60 * 1000)
    const draft = await eventApi(
      'POST',
      '',
      'EO-01',
      completeRequestPayload('AUTO-SPM14-soon', {
        proposedStartAt: start.toISOString(),
        proposedEndAt: end.toISOString(),
      }),
    )
    const submitted = await submitEvent(draft.body.eventId)
    expect(submitted.status).toBe(200)
    expect(submitted.body.status).toMatch(/submitted/i)
  })
})
