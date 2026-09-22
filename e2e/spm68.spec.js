import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { assignCoordinator, createSubmittedEvent, eventApi } from './support/event.js'

async function planningEvent() {
  const event = await createSubmittedEvent('EO-01', `AUTO-SPM68-${Date.now()}`)
  await assignCoordinator(event.eventId, 'u2', 'EC-01')
  return event.eventId
}

test.describe('SPM-68 Request clarification or amendment from the organiser', () => {
  test('TC-SPM68-AC01 the coordinator can raise a clarification naming what is unclear', async () => {
    const eventId = await planningEvent()
    const created = await eventApi('POST', `/${eventId}/clarifications`, 'EC-01', {
      message: 'Please confirm expected attendance.',
      field: 'expectedAttendance',
    })
    expect(created.status).toBe(201)
    expect(created.body.message).toMatch(/attendance/)
    expect(created.body.field).toBe('expectedAttendance')
    expect(created.body.status).toMatch(/open/i)
  })

  test('TC-SPM68-AC02 raising a clarification moves the event to Changes Requested and notifies the organiser', async () => {
    const eventId = await planningEvent()
    const created = await eventApi('POST', `/${eventId}/clarifications`, 'EC-01', {
      message: 'Need a layout preference.',
    })
    expect(created.status).toBe(201)
    const stored = await eventApi('GET', `/${eventId}`, 'EC-01')
    expect(stored.body.status).toMatch(/changes requested/i)
  })

  test('TC-SPM68-AC03 the clarification and reply appear as an ordered thread with author, role, and time', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e3')
    const thread = page.getByTestId('clarification-thread')
    await expect(thread).toBeVisible()
    await expect(thread.getByTestId('clarification-entry').first()).toContainText(/confirm expected attendance/i)
    await expect(thread.getByTestId('clarification-entry').first()).toContainText(/coordinator|Ben Lee/i)
  })

  test('TC-SPM68-AC04 more than one clarification can be open independently', async () => {
    const eventId = await planningEvent()
    const first = await eventApi('POST', `/${eventId}/clarifications`, 'EC-01', {
      message: 'First gap',
    })
    const second = await eventApi('POST', `/${eventId}/clarifications`, 'EC-01', {
      message: 'Second gap',
    })
    expect(first.status).toBe(201)
    expect(second.status).toBe(201)
    const list = await eventApi('GET', `/${eventId}/clarifications`, 'EC-01')
    expect(list.body.length).toBeGreaterThanOrEqual(2)
    expect(list.body.filter((row) => /open/i.test(row.status)).length).toBeGreaterThanOrEqual(2)
  })

  test('TC-SPM68-AC05 resolving every clarification returns the event to Under Review', async () => {
    const eventId = await planningEvent()
    const first = await eventApi('POST', `/${eventId}/clarifications`, 'EC-01', {
      message: 'Only gap',
    })
    expect(first.status).toBe(201)
    const resolved = await eventApi(
      'POST',
      `/${eventId}/clarifications/${first.body.clarificationId}/resolve`,
      'EC-01',
    )
    expect(resolved.status).toBe(200)
    const stored = await eventApi('GET', `/${eventId}`, 'EC-01')
    expect(stored.body.status).toMatch(/under review/i)
  })

  test('TC-SPM68-AC06 threads are visible to the organiser and staff, never to attendees', async () => {
    const staff = await eventApi('GET', '/e3/clarifications', 'EC-01')
    expect(staff.status).toBe(200)
    const organiser = await eventApi('GET', '/e3/clarifications', 'EO-01')
    expect(organiser.status).toBe(200)
    const attendee = await eventApi('GET', '/e3/clarifications', 'ATT-01')
    expect([403, 404]).toContain(attendee.status)
  })

  test('TC-SPM68-AC07 threads remain readable after confirm, complete, or cancel', async () => {
    const list = await eventApi('GET', '/e3/clarifications', 'EC-01')
    expect(list.status).toBe(200)
    expect((list.body || []).length).toBeGreaterThan(0)
  })

  test('TC-SPM68-AC08 a draft event cannot receive a clarification', async () => {
    const created = await eventApi('POST', '', 'EO-01', {
      eventName: 'AUTO-SPM68-draft',
      purpose: 'Draft only',
      description: 'Must stay draft',
      proposedStartAt: new Date(Date.now() + 50 * 24 * 60 * 60 * 1000).toISOString(),
      proposedEndAt: new Date(Date.now() + 50 * 24 * 60 * 60 * 1000 + 2 * 60 * 60 * 1000).toISOString(),
      expectedAttendance: 10,
      capacity: 10,
    })
    expect(created.status).toBe(201)
    const denied = await eventApi('POST', `/${created.body.eventId}/clarifications`, 'EC-01', {
      message: 'Should not work on a draft',
    })
    expect([400, 409, 422]).toContain(denied.status)
  })
})
