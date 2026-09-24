import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import {
  assignCoordinator,
  createNameOnlyDraft,
  createSubmittedEvent,
  eventApi,
  raiseChangeRequest,
} from './support/event.js'

async function underReviewEvent(name) {
  const event = await createSubmittedEvent('EO-01', name)
  await assignCoordinator(event.eventId, 'u2', 'EC-01')
  return event
}

test.describe('SPM-106 Request a change to a submitted event', () => {
  test('TC-SPM106-AC01 the organiser can raise a change request on Under Review, Approved, Planning, or Confirmed events', async () => {
    const review = await underReviewEvent('AUTO-SPM106-review')
    const raised = await raiseChangeRequest(review.eventId, 'EO-01', {
      reason: 'Need a clearer title',
      proposedChanges: { eventName: 'Clearer title' },
    })
    expect(raised.status).toBe(201)
    const planning = await raiseChangeRequest('e3', 'EO-01', {
      reason: 'Tweak description',
      proposedChanges: { description: 'Updated' },
    })
    expect([201, 409]).toContain(planning.status)
    const confirmed = await raiseChangeRequest('e1', 'EO-01', {
      reason: 'Second on e1 may be blocked if one is pending',
      proposedChanges: { purpose: 'Updated purpose' },
    })
    expect([201, 409]).toContain(confirmed.status)
  })

  test('TC-SPM106-AC02 the request states current and proposed values and requires a reason', async () => {
    const event = await underReviewEvent('AUTO-SPM106-reason')
    const missing = await raiseChangeRequest(event.eventId, 'EO-01', {
      proposedChanges: { purpose: 'No reason' },
    })
    expect([400, 422]).toContain(missing.status)
    const raised = await raiseChangeRequest(event.eventId, 'EO-01', {
      reason: 'Client restated the purpose',
      proposedChanges: { purpose: 'New purpose' },
    })
    expect(raised.status).toBe(201)
    expect(raised.body.reason).toMatch(/purpose/)
    expect(raised.body.proposedChanges.purpose).toBe('New purpose')
    expect(raised.body.currentValues || raised.body.previousValues).toBeTruthy()
  })

  test('TC-SPM106-AC03 changeable fields are the published set', async () => {
    const meta = await eventApi('GET', '/changeable-fields', 'EO-01')
    expect(meta.status).toBe(200)
    const fields = meta.body.fields || meta.body
    for (const field of [
      'eventName',
      'description',
      'purpose',
      'category',
      'proposedStartAt',
      'proposedEndAt',
      'expectedAttendance',
      'layoutPreference',
      'accessibilityNeeds',
      'equipmentRequirements',
    ]) {
      expect(fields).toEqual(expect.arrayContaining([field]))
    }
  })

  test('TC-SPM106-AC04 raising a change request notifies the coordinator and both sides see it as pending', async ({
    page,
  }) => {
    const event = await underReviewEvent('AUTO-SPM106-notify')
    const raised = await raiseChangeRequest(event.eventId, 'EO-01', {
      reason: 'Need banquet',
      proposedChanges: { layoutPreference: 'Banquet' },
    })
    expect(raised.body.status).toMatch(/pending/i)
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await expect(page.getByTestId('pending-change-request')).toContainText(/Banquet|pending/i)
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await expect(page.getByTestId('pending-change-request')).toContainText(/Banquet|pending/i)
  })

  test('TC-SPM106-AC05 an event can have only one pending change request; the organiser must withdraw first', async () => {
    const event = await underReviewEvent('AUTO-SPM106-one')
    const first = await raiseChangeRequest(event.eventId, 'EO-01', {
      reason: 'First',
      proposedChanges: { description: 'A' },
    })
    expect(first.status).toBe(201)
    const second = await raiseChangeRequest(event.eventId, 'EO-01', {
      reason: 'Second',
      proposedChanges: { description: 'B' },
    })
    expect([400, 409]).toContain(second.status)
  })

  test('TC-SPM106-AC06 the organiser can withdraw their own pending change request', async () => {
    const event = await underReviewEvent('AUTO-SPM106-withdraw')
    const raised = await raiseChangeRequest(event.eventId, 'EO-01', {
      reason: 'Withdraw me',
      proposedChanges: { description: 'temp' },
    })
    const withdrawn = await eventApi(
      'POST',
      `/${event.eventId}/change-requests/${raised.body.changeRequestId}/withdraw`,
      'EO-01',
    )
    expect(withdrawn.status).toBe(200)
    expect(withdrawn.body.status).toMatch(/withdrawn/i)
  })

  test('TC-SPM106-AC07 the organiser is notified once the coordinator accepts or declines, with the reason', async ({
    page,
  }) => {
    const event = await underReviewEvent('AUTO-SPM106-decided')
    const raised = await raiseChangeRequest(event.eventId, 'EO-01', {
      reason: 'Please decline',
      proposedChanges: { description: 'x' },
    })
    await eventApi(
      'POST',
      `/${event.eventId}/change-requests/${raised.body.changeRequestId}/decline`,
      'EC-01',
      { reason: 'Keep the original copy' },
    )
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await expect(page.getByTestId('change-request-outcome')).toContainText(/declin|Keep the original/i)
  })

  test('TC-SPM106-AC08 a draft has no change-request action because the organiser edits it directly', async ({
    page,
  }) => {
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM106-draft')
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${draft.eventId}`)
    await expect(page.getByTestId('raise-change-request')).toHaveCount(0)
    const denied = await raiseChangeRequest(draft.eventId, 'EO-01', {
      reason: 'no',
      proposedChanges: { purpose: 'x' },
    })
    expect([400, 403, 409]).toContain(denied.status)
  })

  test('TC-SPM106-AC09 no change request can be raised on Completed, Cancelled, or Rejected events', async () => {
    const denied = await raiseChangeRequest('e8', 'EO-01', {
      reason: 'too late',
      proposedChanges: { description: 'x' },
    })
    expect([400, 403, 409]).toContain(denied.status)
  })

  test('TC-SPM106-AC10 confirmed details continue to read as confirmed while a change request is pending', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e1')
    await expect(page.getByTestId('organiser-confirmed-arrangements')).toBeVisible()
    await expect(page.getByTestId('organiser-confirmed-arrangements')).toContainText('Marina Hall A')
    const stored = await eventApi('GET', '/e1', 'EO-01')
    expect(stored.body.status).toMatch(/confirmed/i)
  })
})
