import { test, expect } from '@playwright/test'
import { account } from './support/test-data.js'
import { bearer, firebaseIdToken } from './support/auth.js'
import { equipmentRequestPayload, serviceUrls } from './support/api-data.js'
import { assignCoordinator } from './support/event.js'
import { THEATRE_EVENT, approvedEvent, freshPeriod } from './support/venue-request.js'

// EC-01 is u2 and EC-02 is u6. Every test makes its own event, approved for
// planning and assigned to EC-01, so no test changes a seeded event.

async function api(method, url, id, body) {
  const response = await fetch(url, {
    method,
    headers: {
      ...bearer(await firebaseIdToken(null, account(id))),
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

function requestEquipment(event, id, sequence) {
  return api('POST', `${serviceUrls.equipment}/equipment/requests`, id, equipmentRequestPayload(sequence, event.eventId))
}

function sendVenueRequest(event, id) {
  return api('POST', `${serviceUrls.venue}/venues/bookings`, id, {
    eventId: event.eventId,
    venueId: 'v1',
    ...freshPeriod(),
  })
}

test.describe('SPM-46 Assigned Coordinator Event Permissions (API)', () => {
  test('TC-SPM46-AC01 assigned coordinator can edit, book a venue, and request equipment', async () => {
    const event = await approvedEvent(THEATRE_EVENT)

    const edited = await api('PATCH', `${serviceUrls.event}/events/${event.eventId}`, 'EC-01', {
      description: 'Edited by the assigned coordinator.',
    })
    expect(edited.status, JSON.stringify(edited.body)).toBe(200)

    const booking = await sendVenueRequest(event, 'EC-01')
    expect(booking.status, JSON.stringify(booking.body)).toBe(201)
    expect(booking.body.status).toBe('pending')

    const equipment = await requestEquipment(event, 'EC-01', 71)
    expect(equipment.status, JSON.stringify(equipment.body)).toBe(201)
    expect(equipment.body.status).toBe('pending')

    const refined = await api(
      'PATCH',
      `${serviceUrls.equipment}/equipment/requests/${equipment.body.requestId}/details`,
      'EC-01',
      { quantity: 2 },
    )
    expect(refined.status, JSON.stringify(refined.body)).toBe(200)
  })

  test('TC-SPM46-AC01 other roles cannot act on the assigned event', async () => {
    const event = await approvedEvent(THEATRE_EVENT)
    for (const id of ['VS-01', 'TS-01', 'EO-01', 'ATT-01']) {
      const booking = await sendVenueRequest(event, id)
      expect(booking.status, `${id} venue booking ${JSON.stringify(booking.body)}`).toBe(403)

      const equipment = await requestEquipment(event, id, 72)
      expect(equipment.status, `${id} equipment request ${JSON.stringify(equipment.body)}`).toBe(403)
    }
  })

  test('TC-SPM46-AC01 unassigned coordinator is refused every planning action', async () => {
    const event = await approvedEvent(THEATRE_EVENT)
    const equipment = await requestEquipment(event, 'EC-01', 73)
    expect(equipment.status, JSON.stringify(equipment.body)).toBe(201)

    const edit = await api('PATCH', `${serviceUrls.event}/events/${event.eventId}`, 'EC-02', {
      description: 'Not mine to edit.',
    })
    expect(edit.status, JSON.stringify(edit.body)).toBe(403)

    const booking = await sendVenueRequest(event, 'EC-02')
    expect(booking.status, JSON.stringify(booking.body)).toBe(403)
    expect(booking.body.detail).toBe('Only the coordinator assigned to this event can request a venue for it.')

    const newEquipment = await requestEquipment(event, 'EC-02', 74)
    expect(newEquipment.status, JSON.stringify(newEquipment.body)).toBe(403)
    expect(newEquipment.body.detail).toBe('Only the coordinator assigned to this event can request equipment for it.')

    const change = await api(
      'PATCH',
      `${serviceUrls.equipment}/equipment/requests/${equipment.body.requestId}/details`,
      'EC-02',
      { quantity: 5 },
    )
    expect(change.status, JSON.stringify(change.body)).toBe(403)
    expect(change.body.detail).toBe('Only the coordinator assigned to this event can change its equipment requests.')
  })

  test('TC-SPM46-AC01 confirming event arrangements is limited to the assigned coordinator', async () => {
    test.skip(true, 'Confirming an event is SPM-72, which is not built yet; remove this skip when it ships.')
  })

  test('TC-SPM46-AC02 unassigned internal staff can read event details', async () => {
    const event = await approvedEvent(THEATRE_EVENT)
    for (const id of ['VS-01', 'TS-01', 'EC-02']) {
      const response = await api('GET', `${serviceUrls.event}/events/${event.eventId}`, id)
      expect(response.status, `${id} GET event ${JSON.stringify(response.body)}`).toBe(200)
      expect(response.body.eventId).toBe(event.eventId)
      expect(response.body.eventName).toBe(event.eventName)
      expect(response.body.coordinatorId).toBe('u2')
    }
  })

  test('TC-SPM46-AC03 reassignment moves every planning right to the new coordinator at once', async () => {
    const event = await approvedEvent(THEATRE_EVENT)
    const sent = await sendVenueRequest(event, 'EC-01')
    expect(sent.status, JSON.stringify(sent.body)).toBe(201)
    const equipment = await requestEquipment(event, 'EC-01', 75)
    expect(equipment.status, JSON.stringify(equipment.body)).toBe(201)

    const assignment = await assignCoordinator(event.eventId, 'u6')
    expect(assignment.coordinatorId).toBe('u6')

    // The previous coordinator, still signed in, is refused straight away.
    const oldEdit = await api('PATCH', `${serviceUrls.event}/events/${event.eventId}`, 'EC-01', {
      description: 'Too late.',
    })
    expect(oldEdit.status, JSON.stringify(oldEdit.body)).toBe(403)
    const oldWithdraw = await api('POST', `${serviceUrls.venue}/venues/bookings/${sent.body.bookingId}/withdraw`, 'EC-01')
    expect(oldWithdraw.status, JSON.stringify(oldWithdraw.body)).toBe(403)
    const oldEquipment = await requestEquipment(event, 'EC-01', 76)
    expect(oldEquipment.status, JSON.stringify(oldEquipment.body)).toBe(403)
    const oldChange = await api(
      'PATCH',
      `${serviceUrls.equipment}/equipment/requests/${equipment.body.requestId}/details`,
      'EC-01',
      { quantity: 3 },
    )
    expect(oldChange.status, JSON.stringify(oldChange.body)).toBe(403)

    // The new coordinator can take over, including the request the previous one sent.
    const newEdit = await api('PATCH', `${serviceUrls.event}/events/${event.eventId}`, 'EC-02', {
      description: 'Taken over by the new coordinator.',
    })
    expect(newEdit.status, JSON.stringify(newEdit.body)).toBe(200)
    const newWithdraw = await api('POST', `${serviceUrls.venue}/venues/bookings/${sent.body.bookingId}/withdraw`, 'EC-02')
    expect(newWithdraw.status, JSON.stringify(newWithdraw.body)).toBe(200)
    expect(newWithdraw.body.status).toBe('withdrawn')
    const newBooking = await sendVenueRequest(event, 'EC-02')
    expect(newBooking.status, JSON.stringify(newBooking.body)).toBe(201)
    const newChange = await api(
      'PATCH',
      `${serviceUrls.equipment}/equipment/requests/${equipment.body.requestId}/details`,
      'EC-02',
      { quantity: 3 },
    )
    expect(newChange.status, JSON.stringify(newChange.body)).toBe(200)
    expect(newChange.body.quantity).toBe(3)
  })
})
