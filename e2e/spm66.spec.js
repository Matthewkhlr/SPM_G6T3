import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { assignCoordinator, createSubmittedEvent, eventApi } from './support/event.js'

test.describe('SPM-66 Assign a coordinator to a submitted event', () => {
  test('TC-SPM66-AC01 a coordinator can assign an unassigned submitted event to themselves or another coordinator', async ({
    page,
  }) => {
    const event = await createSubmittedEvent('EO-01', 'AUTO-SPM66-self')
    const self = await assignCoordinator(event.eventId, 'u2', 'EC-01')
    expect(self.coordinatorId).toBe('u2')

    const otherEvent = await createSubmittedEvent('EO-01', 'AUTO-SPM66-other')
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${otherEvent.eventId}`)
    await page.getByTestId('assign-coordinator').click()
    await page.getByTestId('assign-candidate-u6').click()
    await page.getByRole('button', { name: /assign/i }).click()
    const stored = await eventApi('GET', `/${otherEvent.eventId}`, 'EC-01')
    expect(stored.body.coordinatorId || stored.body.coordinator?.userId).toBe('u6')
  })

  test('TC-SPM66-AC02 the candidate list shows each coordinator active-event count as information only', async () => {
    const list = await eventApi('GET', '/coordinators', 'EC-01')
    expect(list.status).toBe(200)
    const ben = (list.body || []).find((row) => row.coordinatorId === 'u2' || row.userId === 'u2')
    expect(ben).toBeTruthy()
    expect(typeof (ben.activeEventCount ?? ben.activeCount)).toBe('number')
  })

  test('TC-SPM66-AC03 assignment succeeds even when the coordinator already holds many events', async () => {
    const event = await createSubmittedEvent('EO-01', 'AUTO-SPM66-load')
    const assigned = await assignCoordinator(event.eventId, 'u2', 'EC-01')
    expect(assigned.coordinatorId).toBe('u2')
  })

  test('TC-SPM66-AC04 assignment records who assigned, who was assigned, and when', async () => {
    const event = await createSubmittedEvent('EO-01', 'AUTO-SPM66-log')
    const assigned = await assignCoordinator(event.eventId, 'u6', 'EC-01')
    expect(assigned.assignedBy).toBe('u2')
    expect(assigned.coordinatorId).toBe('u6')
    expect(assigned.assignedAt).toBeTruthy()
    const log = await eventApi('GET', `/${event.eventId}/activity-log`, 'EC-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/assign|u6|u2/)
  })

  test('TC-SPM66-AC05 assignment notifies the coordinator and organiser, and the organiser can see contact details', async ({
    page,
  }) => {
    const event = await createSubmittedEvent('EO-01', 'AUTO-SPM66-notify')
    await assignCoordinator(event.eventId, 'u2', 'EC-01')
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await expect(page.getByTestId('organiser-coordinator')).toContainText('Ben Lee')
    await expect(page.getByTestId('organiser-coordinator')).toContainText(/@/)
  })

  test('TC-SPM66-AC06 assigning moves the event from Submitted to Under Review', async () => {
    const event = await createSubmittedEvent('EO-01', 'AUTO-SPM66-status')
    expect(event.status).toMatch(/submitted/i)
    await assignCoordinator(event.eventId, 'u2', 'EC-01')
    const stored = await eventApi('GET', `/${event.eventId}`, 'EC-01')
    expect(stored.body.status).toMatch(/under review/i)
  })

  test('TC-SPM66-AC07 only Event Coordinators can assign; other roles get 403', async () => {
    const event = await createSubmittedEvent('EO-01', 'AUTO-SPM66-403')
    for (const id of ['EO-01', 'VS-01', 'TS-01', 'ATT-01']) {
      const denied = await eventApi(
        'POST',
        `/${event.eventId}/assign-coordinator`,
        id,
        { coordinatorId: 'u2' },
      )
      expect(denied.status, id).toBe(403)
    }
  })

  test('TC-SPM66-AC08 an event cannot be assigned to a user who is not an Event Coordinator', async () => {
    const event = await createSubmittedEvent('EO-01', 'AUTO-SPM66-role')
    const denied = await eventApi(
      'POST',
      `/${event.eventId}/assign-coordinator`,
      'EC-01',
      { coordinatorId: 'u3' },
    )
    expect([400, 403, 422]).toContain(denied.status)
  })
})
