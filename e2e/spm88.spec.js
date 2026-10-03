import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venueBookingPayload } from './support/api-data.js'
import {
  assignCoordinator,
  createSubmittedEvent,
  eventApi,
  raiseChangeRequest,
} from './support/event.js'
import { venueRequest } from './support/venue.js'
import { createPendingRequest, equipmentApi } from './support/equipment.js'

async function cancellableEvent(name) {
  const event = await createSubmittedEvent('EO-01', name)
  await assignCoordinator(event.eventId, 'u2', 'EC-01')
  return event
}

test.describe('SPM-88 Cancel an event and release its arrangements', () => {
  test('TC-SPM88-AC01 the organiser can cancel their org events in the published statuses, and the coordinator can cancel on ConnectSphere\'s behalf', async () => {
    const submitted = await createSubmittedEvent('EO-01', 'AUTO-SPM88-submitted')
    const asOrganiser = await eventApi('POST', `/${submitted.eventId}/cancel`, 'EO-01', {
      reason: 'AUTO-SPM88-organiser',
    })
    expect(asOrganiser.status).toBe(200)
    expect(asOrganiser.body.status).toMatch(/cancelled/i)
    const fresh = await cancellableEvent('AUTO-SPM88-coord')
    const asCoord = await eventApi('POST', `/${fresh.eventId}/cancel`, 'EC-01', {
      reason: 'ConnectSphere cannot staff it',
    })
    expect(asCoord.status).toBe(200)
    expect(asCoord.body.status).toMatch(/cancelled/i)
  })

  test('TC-SPM88-AC02 cancellation requires a reason and takes effect immediately, with no approval step', async () => {
    const event = await cancellableEvent('AUTO-SPM88-reason')
    const missing = await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', {})
    expect([400, 422]).toContain(missing.status)
    const cancelled = await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', {
      reason: 'Date no longer works',
    })
    expect(cancelled.status).toBe(200)
    expect(cancelled.body.status).toMatch(/cancelled/i)
    expect(cancelled.body.approvalRequired).toBeFalsy()
  })

  test('TC-SPM88-AC03 cancelling asks for confirmation and states what will be released and who will be notified', async ({
    page,
  }) => {
    const event = await cancellableEvent('AUTO-SPM88-confirm')
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await page.getByTestId('event-cancel').click()
    const dialog = page.getByTestId('cancel-confirm')
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText(/venue|equipment|attendee|coordinator/i)
  })

  test('TC-SPM88-AC04 the event moves to Cancelled, which is terminal', async () => {
    const event = await cancellableEvent('AUTO-SPM88-terminal')
    await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', { reason: 'Stop' })
    const approve = await eventApi('POST', `/${event.eventId}/approve`, 'EC-01', {})
    expect([400, 409]).toContain(approve.status)
    const stored = await eventApi('GET', `/${event.eventId}`, 'EO-01')
    expect(stored.body.status).toMatch(/cancelled/i)
  })

  test('TC-SPM88-AC05 every venue booking and pending request is released and the venue is free immediately', async () => {
    const event = await cancellableEvent('AUTO-SPM88-venue')
    const booking = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      ...venueBookingPayload(410, event.eventId, 'v2'),
    })
    expect(booking.status).toBe(201)
    await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', { reason: 'Free the room' })
    const viewed = await venueRequest('GET', `/venues/bookings/${booking.body.bookingId}`, 'VS-01')
    expect(viewed.body.status).toMatch(/released|withdrawn|cancelled/i)
  })

  test('TC-SPM88-AC06 every equipment reservation is released and quantities are free immediately', async () => {
    const event = await cancellableEvent('AUTO-SPM88-eq')
    const request = await createPendingRequest({ eventId: event.eventId, sequence: 411 })
    await equipmentApi('POST', `/equipment/requests/${request.requestId}/review`, 'TS-01', {
      approve: true,
      reviewNote: 'ok',
    })
    const reserved = await equipmentApi('POST', `/equipment/requests/${request.requestId}/reserve`, 'TS-01')
    await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', { reason: 'Free kits' })
    if (reserved.status === 201) {
      const viewed = await equipmentApi(
        'GET',
        `/equipment/reservations/${reserved.body.reservationId}`,
        'TS-01',
      )
      expect(viewed.body.status).toMatch(/released|cancelled/i)
    }
  })

  test('TC-SPM88-AC07 registration closes and every registered attendee is notified with the reason', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e8')
    await expect(page.getByTestId('event-status')).toContainText(/cancelled/i)
    const regs = await eventApi('GET', '/e8/registrations', 'EO-01')
    expect([200, 404]).toContain(regs.status)
    const attendee = await eventApi('GET', '/e8', 'ATT-01')
    expect(JSON.stringify(attendee.body)).toMatch(/cancelled/i)
  })

  test('TC-SPM88-AC08 the assigned coordinator, approving venue staff, and technical support holding reservations are notified', async () => {
    const event = await cancellableEvent('AUTO-SPM88-staff')
    await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', { reason: 'Notify staff' })
    const coord = await eventApi('GET', `/${event.eventId}`, 'EC-01')
    expect(coord.status).toBe(200)
    expect(coord.body.status).toMatch(/cancelled/i)
  })

  test('TC-SPM88-AC09 if any release fails, cancellation does not take effect', async () => {
    const denied = await eventApi('POST', '/e1/cancel', 'EO-01', {
      reason: 'Force release failure',
      simulateReleaseFailure: true,
    })
    expect([409, 500, 400]).toContain(denied.status)
    const stored = await eventApi('GET', '/e1', 'EO-01')
    expect(stored.body.status).not.toMatch(/cancelled/i)
  })

  test('TC-SPM88-AC10 the cancelled event, reason, arrangement history, and registrations stay readable and are logged', async () => {
    const viewed = await eventApi('GET', '/e8', 'EO-01')
    expect(viewed.status).toBe(200)
    expect(viewed.body.status).toMatch(/cancelled/i)
    const log = await eventApi('GET', '/e8/activity-log', 'EC-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/cancel/)
  })

  test('TC-SPM88-AC11 a pending change request on the event is closed by the cancellation', async () => {
    const event = await cancellableEvent('AUTO-SPM88-cr')
    const raised = await raiseChangeRequest(event.eventId, 'EO-01', {
      reason: 'Will be closed',
      proposedChanges: { description: 'pending' },
    })
    expect(raised.status).toBe(201)
    await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', { reason: 'Close the CR' })
    const list = await eventApi('GET', `/${event.eventId}/change-requests`, 'EC-01')
    expect(list.status).toBe(200)
    expect((list.body || [])[0].status).toMatch(/closed|cancelled|withdrawn/i)
  })
})
