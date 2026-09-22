import { test, expect } from '@playwright/test'
import { account } from './support/test-data.js'
import { bearer, firebaseIdToken } from './support/auth.js'
import {
  equipmentRequestPayload,
  serviceUrls,
  venueBookingPayload,
} from './support/api-data.js'

const ASSIGNMENT_GATE =
  'Assignment-gated 403 is not implemented; venue and equipment APIs currently allow any coordinator.'

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

test.describe('SPM-46 Assigned Coordinator Event Permissions — API', () => {
  test('TC-SPM46-AC01 assigned coordinator can book venue and request equipment', async () => {
    const booking = await api(
      'POST',
      `${serviceUrls.venue}/venues/bookings`,
      'EC-01',
      venueBookingPayload(61),
    )
    expect(booking.status, JSON.stringify(booking.body)).toBe(201)
    expect(booking.body.status).toBe('pending')

    const equipment = await api(
      'POST',
      `${serviceUrls.equipment}/equipment/requests`,
      'EC-01',
      equipmentRequestPayload(71),
    )
    expect(equipment.status, JSON.stringify(equipment.body)).toBe(201)
    expect(equipment.body.status).toBe('pending')
  })

  test('TC-SPM46-AC01 other roles cannot act on the assigned event', async () => {
    for (const id of ['VS-01', 'TS-01', 'EO-01', 'ATT-01']) {
      const booking = await api(
        'POST',
        `${serviceUrls.venue}/venues/bookings`,
        id,
        venueBookingPayload(62),
      )
      expect(booking.status, `${id} venue booking ${JSON.stringify(booking.body)}`).toBe(403)

      const equipment = await api(
        'POST',
        `${serviceUrls.equipment}/equipment/requests`,
        id,
        equipmentRequestPayload(72),
      )
      expect(equipment.status, `${id} equipment request ${JSON.stringify(equipment.body)}`).toBe(403)
    }
  })

  test('TC-SPM46-AC01 unassigned coordinator is rejected on e1', async () => {
    test.skip(true, ASSIGNMENT_GATE)

    const booking = await api(
      'POST',
      `${serviceUrls.venue}/venues/bookings`,
      'EC-02',
      venueBookingPayload(63),
    )
    expect(booking.status).toBe(403)

    const equipment = await api(
      'POST',
      `${serviceUrls.equipment}/equipment/requests`,
      'EC-02',
      equipmentRequestPayload(73),
    )
    expect(equipment.status).toBe(403)
  })

  test('TC-SPM46-AC02 unassigned internal staff can read event details', async () => {
    for (const id of ['VS-01', 'TS-01', 'EC-02']) {
      const response = await api('GET', `${serviceUrls.event}/events/e1`, id)
      expect(response.status, `${id} GET /events/e1 ${JSON.stringify(response.body)}`).toBe(200)
      expect(response.body.eventId).toBe('e1')
      expect(response.body.eventName).toBeTruthy()
      expect(response.body.status).toBeTruthy()
    }
  })

  test('TC-SPM46-AC03 reassignment updates the coordinator on e3', async () => {
    try {
      const assigned = await api(
        'POST',
        `${serviceUrls.event}/events/e3/assign-coordinator`,
        'EC-01',
        { coordinatorId: 'u6' },
      )
      expect(assigned.status, JSON.stringify(assigned.body)).toBe(201)
      expect(assigned.body.eventId).toBe('e3')
      expect(assigned.body.coordinatorId).toBe('u6')
      expect(assigned.body.assignedBy).toBe('u2')
    } finally {
      const restored = await api(
        'POST',
        `${serviceUrls.event}/events/e3/assign-coordinator`,
        'EC-01',
        { coordinatorId: 'u2' },
      )
      expect(restored.status, JSON.stringify(restored.body)).toBe(201)
      expect(restored.body.coordinatorId).toBe('u2')
    }
  })

  test('TC-SPM46-AC03 previous coordinator loses action rights after reassignment', async () => {
    test.skip(true, ASSIGNMENT_GATE)

    try {
      const assigned = await api(
        'POST',
        `${serviceUrls.event}/events/e3/assign-coordinator`,
        'EC-01',
        { coordinatorId: 'u6' },
      )
      expect(assigned.status).toBe(201)

      const denied = await api(
        'POST',
        `${serviceUrls.venue}/venues/bookings`,
        'EC-01',
        venueBookingPayload(64, 'e3'),
      )
      expect(denied.status).toBe(403)

      const allowed = await api(
        'POST',
        `${serviceUrls.venue}/venues/bookings`,
        'EC-02',
        venueBookingPayload(65, 'e3'),
      )
      expect(allowed.status).toBe(201)
    } finally {
      await api('POST', `${serviceUrls.event}/events/e3/assign-coordinator`, 'EC-01', {
        coordinatorId: 'u2',
      })
    }
  })
})
