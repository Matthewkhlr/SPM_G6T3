import { test, expect } from '@playwright/test'
import { account } from './support/test-data.js'
import { bearer, firebaseIdToken } from './support/auth.js'
import {
  equipmentRequestPayload,
  serviceUrls,
  venueBookingPayload,
} from './support/api-data.js'

test.describe('SPM-45 Role-Based Feature Access Control — API', () => {
  const tokens = {}

  test.beforeAll(async ({ request }) => {
    for (const id of ['EO-01', 'EC-01', 'VS-01', 'TS-01', 'ATT-01']) {
      tokens[id] = await firebaseIdToken(request, account(id))
    }
  })

  test('TC-SPM45-AC01 Venue Staff decisions and forbidden actions', async ({ request }) => {
    const approveCandidate = await request.post(`${serviceUrls.venue}/venues/bookings`, {
      headers: bearer(tokens['EC-01']),
      data: venueBookingPayload(31),
    })
    expect(approveCandidate.status()).toBe(201)
    const approveBooking = await approveCandidate.json()
    expect(approveBooking.status).toBe('pending')

    const rejectCandidate = await request.post(`${serviceUrls.venue}/venues/bookings`, {
      headers: bearer(tokens['EC-01']),
      data: venueBookingPayload(32),
    })
    expect(rejectCandidate.status()).toBe(201)
    const rejectBooking = await rejectCandidate.json()

    const approved = await request.post(
      `${serviceUrls.venue}/venues/bookings/${approveBooking.bookingId}/approve`,
      {
        headers: bearer(tokens['VS-01']),
        data: { reason: 'AUTO-SPM45 venue available' },
      },
    )
    expect(approved.status()).toBe(200)
    expect((await approved.json()).status).toBe('approved')

    const rejected = await request.post(
      `${serviceUrls.venue}/venues/bookings/${rejectBooking.bookingId}/reject`,
      {
        headers: bearer(tokens['VS-01']),
        data: { reason: 'AUTO-SPM45 turnaround conflict' },
      },
    )
    expect(rejected.status()).toBe(200)
    const rejectedBody = await rejected.json()
    expect(rejectedBody.status).toBe('rejected')
    expect(rejectedBody.decisionReason).toBe('AUTO-SPM45 turnaround conflict')

    const equipmentDenied = await request.post(`${serviceUrls.equipment}/equipment/requests`, {
      headers: bearer(tokens['VS-01']),
      data: equipmentRequestPayload(51),
    })
    expect(equipmentDenied.status()).toBe(403)

    const assignmentDenied = await request.post(
      `${serviceUrls.event}/events/e1/assign-coordinator`,
      {
        headers: bearer(tokens['VS-01']),
        data: { coordinatorId: 'u2' },
      },
    )
    expect(assignmentDenied.status()).toBe(403)
  })

  test('TC-SPM45-AC02 Technical Support reviews and reserves equipment only', async ({
    request,
  }) => {
    const created = await request.post(`${serviceUrls.equipment}/equipment/requests`, {
      headers: bearer(tokens['EC-01']),
      data: equipmentRequestPayload(52),
    })
    expect(created.status()).toBe(201)
    const equipmentRequest = await created.json()
    expect(equipmentRequest.status).toBe('pending')
    expect(equipmentRequest.technicalRequirements).toContain('AUTO-SPM45')

    const reviewed = await request.post(
      `${serviceUrls.equipment}/equipment/requests/${equipmentRequest.requestId}/review`,
      {
        headers: bearer(tokens['TS-01']),
        data: { approve: true, reviewNote: 'AUTO-SPM45 stock confirmed' },
      },
    )
    expect(reviewed.status()).toBe(200)
    expect((await reviewed.json()).status).toBe('approved')

    const reserved = await request.post(
      `${serviceUrls.equipment}/equipment/requests/${equipmentRequest.requestId}/reserve`,
      { headers: bearer(tokens['TS-01']) },
    )
    expect(reserved.status()).toBe(201)
    expect((await reserved.json()).status).toBe('active')

    const bookingResponse = await request.post(`${serviceUrls.venue}/venues/bookings`, {
      headers: bearer(tokens['EC-01']),
      data: venueBookingPayload(33),
    })
    expect(bookingResponse.status()).toBe(201)
    const booking = await bookingResponse.json()

    for (const decision of ['approve', 'reject']) {
      const denied = await request.post(
        `${serviceUrls.venue}/venues/bookings/${booking.bookingId}/${decision}`,
        {
          headers: bearer(tokens['TS-01']),
          data: { reason: 'AUTO-SPM45 forbidden technical decision' },
        },
      )
      expect(denied.status()).toBe(403)
    }

    // A later valid Venue Staff decision proves the forbidden calls left it pending.
    const validDecision = await request.post(
      `${serviceUrls.venue}/venues/bookings/${booking.bookingId}/approve`,
      {
        headers: bearer(tokens['VS-01']),
        data: { reason: 'AUTO-SPM45 unchanged after forbidden calls' },
      },
    )
    expect(validDecision.status()).toBe(200)
    expect((await validDecision.json()).status).toBe('approved')
  })

  test('TC-SPM45-AC03 Coordinator assigns and requests but cannot decide booking', async ({
    request,
  }) => {
    const assignment = await request.post(`${serviceUrls.event}/events/e1/assign-coordinator`, {
      headers: bearer(tokens['EC-01']),
      data: { coordinatorId: 'u2' },
    })
    expect(assignment.status()).toBe(201)
    expect((await assignment.json()).coordinatorId).toBe('u2')

    const bookingResponse = await request.post(`${serviceUrls.venue}/venues/bookings`, {
      headers: bearer(tokens['EC-01']),
      data: venueBookingPayload(34),
    })
    expect(bookingResponse.status()).toBe(201)
    const booking = await bookingResponse.json()

    const equipment = await request.post(`${serviceUrls.equipment}/equipment/requests`, {
      headers: bearer(tokens['EC-01']),
      data: equipmentRequestPayload(53),
    })
    expect(equipment.status()).toBe(201)
    expect((await equipment.json()).status).toBe('pending')

    for (const decision of ['approve', 'reject']) {
      const denied = await request.post(
        `${serviceUrls.venue}/venues/bookings/${booking.bookingId}/${decision}`,
        {
          headers: bearer(tokens['EC-01']),
          data: { reason: 'AUTO-SPM45 coordinator cannot self-approve' },
        },
      )
      expect(denied.status()).toBe(403)
    }

    const validDecision = await request.post(
      `${serviceUrls.venue}/venues/bookings/${booking.bookingId}/approve`,
      {
        headers: bearer(tokens['VS-01']),
        data: { reason: 'AUTO-SPM45 approved by Venue Staff' },
      },
    )
    expect(validDecision.status()).toBe(200)
    expect((await validDecision.json()).reviewedBy).toBe('u3')
  })

  test('TC-SPM45-AC04 wrong-role API matrix returns 403', async ({ request }) => {
    const pendingResponse = await request.post(`${serviceUrls.venue}/venues/bookings`, {
      headers: bearer(tokens['EC-01']),
      data: venueBookingPayload(35),
    })
    expect(pendingResponse.status()).toBe(201)
    const pending = await pendingResponse.json()

    const attempts = [
      {
        name: 'Venue Staff cannot assign coordinators',
        call: () =>
          request.post(`${serviceUrls.event}/events/e1/assign-coordinator`, {
            headers: bearer(tokens['VS-01']),
            data: { coordinatorId: 'u2' },
          }),
      },
      {
        name: 'Technical Support cannot create venue bookings',
        call: () =>
          request.post(`${serviceUrls.venue}/venues/bookings`, {
            headers: bearer(tokens['TS-01']),
            data: venueBookingPayload(36),
          }),
      },
      {
        name: 'Coordinator cannot approve venue bookings',
        call: () =>
          request.post(`${serviceUrls.venue}/venues/bookings/${pending.bookingId}/approve`, {
            headers: bearer(tokens['EC-01']),
            data: { reason: 'AUTO-SPM45 forbidden' },
          }),
      },
      {
        name: 'Organiser cannot create equipment requests',
        call: () =>
          request.post(`${serviceUrls.equipment}/equipment/requests`, {
            headers: bearer(tokens['EO-01']),
            data: equipmentRequestPayload(54),
          }),
      },
      {
        name: 'Attendee cannot reject venue bookings',
        call: () =>
          request.post(`${serviceUrls.venue}/venues/bookings/${pending.bookingId}/reject`, {
            headers: bearer(tokens['ATT-01']),
            data: { reason: 'AUTO-SPM45 forbidden' },
          }),
      },
    ]

    for (const attempt of attempts) {
      const response = await attempt.call()
      expect(response.status(), attempt.name).toBe(403)
      expect((await response.json()).detail, attempt.name).toMatch(/permission|role/i)
    }

    const unchanged = await request.post(
      `${serviceUrls.venue}/venues/bookings/${pending.bookingId}/approve`,
      {
        headers: bearer(tokens['VS-01']),
        data: { reason: 'AUTO-SPM45 still pending after forbidden matrix' },
      },
    )
    expect(unchanged.status()).toBe(200)
    expect((await unchanged.json()).status).toBe('approved')
  })
})
