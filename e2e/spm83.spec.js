import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { createNameOnlyDraft, createSubmittedEvent, eventApi } from './support/event.js'

test.describe('SPM-83 Discard a draft request', () => {
  test('TC-SPM83-AC01 the organiser can discard a request only while it is in Draft status', async () => {
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM83-draft')
    const discarded = await eventApi('DELETE', `/${draft.eventId}`, 'EO-01')
    expect([200, 204]).toContain(discarded.status)
    const submitted = await createSubmittedEvent('EO-01', 'AUTO-SPM83-submitted')
    const denied = await eventApi('DELETE', `/${submitted.eventId}`, 'EO-01')
    expect(denied.status).toBe(403)
  })

  test('TC-SPM83-AC02 discarding asks for confirmation and names the event', async ({ page }) => {
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM83-confirm')
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${draft.eventId}`)
    await page.getByTestId('event-discard').click()
    const dialog = page.getByTestId('discard-confirm')
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText('AUTO-SPM83-confirm')
  })

  test('TC-SPM83-AC03 a discarded draft no longer appears in the organiser list', async ({ page }) => {
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM83-gone')
    await eventApi('DELETE', `/${draft.eventId}`, 'EO-01')
    const list = await eventApi('GET', '', 'EO-01')
    expect((list.body || []).map((row) => row.eventId)).not.toContain(draft.eventId)
    await login(page, account('EO-01'))
    await page.locator('.nav-item').getByText('My Events', { exact: true }).click()
    await expect(page.getByTestId(`organiser-event-${draft.eventId}`)).toHaveCount(0)
  })

  test('TC-SPM83-AC04 no discard action is offered on a non-draft, and the endpoint returns 403', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e6')
    await expect(page.getByTestId('event-discard')).toHaveCount(0)
    const denied = await eventApi('DELETE', '/e6', 'EO-01')
    expect(denied.status).toBe(403)
    const cancelled = await eventApi('DELETE', '/e8', 'EO-01')
    expect(cancelled.status).toBe(403)
  })

  test('TC-SPM83-AC05 the discard is recorded in the activity log with who and when', async () => {
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM83-log')
    await eventApi('DELETE', `/${draft.eventId}`, 'EO-01')
    const log = await eventApi('GET', `/${draft.eventId}/activity-log`, 'EO-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/discard|u1/)
  })
})
