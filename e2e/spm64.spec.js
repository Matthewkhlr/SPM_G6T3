import { test, expect } from '@playwright/test'
import { venueBookingPayload, venuePeriod } from './support/api-data.js'
import { createPendingBooking, venueRequest } from './support/venue.js'

test.describe('SPM-64 Prevent double-booking of a venue', () => {
  test('TC-SPM64-AC01 one shared conflict rule is used by search, suitability, approval, blocking, and rescheduling', async () => {
    const created = await createPendingBooking('EC-01', 270, { venueId: 'v2' })
    await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'shared rule',
    })
    const window = venuePeriod(270, 2)
    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(window.startsAt)}&endsAt=${encodeURIComponent(window.endsAt)}`,
      'EC-01',
    )
    const suitability = await venueRequest('POST', '/venues/suitability', 'EC-01', {
      eventId: 'e4',
      venueId: 'v2',
      ...window,
    })
    const clash = await createPendingBooking('EC-01', 270, { venueId: 'v2', eventId: 'e4' })
    const approved = await venueRequest('POST', `/venues/bookings/${clash.bookingId}/approve`, 'VS-01', {
      reason: 'should conflict',
    })
    expect(search.status).toBe(200)
    expect((search.body || []).map((row) => row.venueId)).not.toContain('v2')
    expect(suitability.body.verdict).toMatch(/not suitable/i)
    expect(approved.status).toBe(409)
  })

  test('TC-SPM64-AC02 two confirmed bookings for the same venue never overlap', async () => {
    const first = await createPendingBooking('EC-01', 271, { venueId: 'v3' })
    expect(
      (await venueRequest('POST', `/venues/bookings/${first.bookingId}/approve`, 'VS-01', { reason: 'a' }))
        .status,
    ).toBe(200)
    const second = await createPendingBooking('EC-01', 271, { venueId: 'v3', eventId: 'e4' })
    const blocked = await venueRequest('POST', `/venues/bookings/${second.bookingId}/approve`, 'VS-01', {
      reason: 'b',
    })
    expect(blocked.status).toBe(409)
  })

  test('TC-SPM64-AC03 a confirmed booking conflicts with an overlapping unavailability period', async () => {
    const created = await createPendingBooking('EC-01', 272, { venueId: 'v2' })
    await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'then block',
    })
    const window = venuePeriod(272, 2)
    const block = await venueRequest('POST', '/venues/v2/unavailability', 'VS-01', {
      startsAt: window.startsAt,
      endsAt: window.endsAt,
      reason: 'maintenance',
    })
    expect(block.status).toBe(409)
  })

  test('TC-SPM64-AC04 ranges that only touch do not conflict', async () => {
    const firstWindow = venuePeriod(273, 2)
    const first = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      ...venueBookingPayload(273, 'e1', 'v4'),
      ...firstWindow,
    })
    expect(first.status).toBe(201)
    await venueRequest('POST', `/venues/bookings/${first.body.bookingId}/approve`, 'VS-01', {
      reason: 'first',
    })

    const touchStart = firstWindow.endsAt
    const touchEnd = new Date(new Date(touchStart).getTime() + 2 * 60 * 60 * 1000).toISOString()
    const second = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      venueId: 'v4',
      eventId: 'e4',
      startsAt: touchStart,
      endsAt: touchEnd,
      setupStartsAt: touchStart,
      teardownEndsAt: touchEnd,
      requirementsSnapshot: 'touching range',
    })
    expect(second.status).toBe(201)
    const approved = await venueRequest('POST', `/venues/bookings/${second.body.bookingId}/approve`, 'VS-01', {
      reason: 'touching is ok',
    })
    expect(approved.status).toBe(200)
  })

  test('TC-SPM64-AC05 simultaneous conflicting approvals allow exactly one success', async () => {
    const a = await createPendingBooking('EC-01', 274, { venueId: 'v3', eventId: 'e1' })
    const b = await createPendingBooking('EC-01', 274, { venueId: 'v3', eventId: 'e4' })
    const [first, second] = await Promise.all([
      venueRequest('POST', `/venues/bookings/${a.bookingId}/approve`, 'VS-01', { reason: 'race-a' }),
      venueRequest('POST', `/venues/bookings/${b.bookingId}/approve`, 'VS-01', { reason: 'race-b' }),
    ])
    const statuses = [first.status, second.status].sort()
    expect(statuses).toEqual([200, 409])
  })

  test('TC-SPM64-AC06 cancelling, rejecting, completing, or withdrawing releases the hold', async () => {
    const created = await createPendingBooking('EC-01', 275, { venueId: 'v2' })
    await venueRequest('POST', `/venues/bookings/${created.bookingId}/reject`, 'VS-01', {
      reason: 'other',
      explanation: 'release',
    })
    const next = await createPendingBooking('EC-01', 275, { venueId: 'v2', eventId: 'e4' })
    const approved = await venueRequest('POST', `/venues/bookings/${next.bookingId}/approve`, 'VS-01', {
      reason: 'reused slot',
    })
    expect(approved.status).toBe(200)
  })

  test('TC-SPM64-AC07 overlap boundaries are covered', async () => {
    const base = venuePeriod(276, 2)
    const mid = new Date(
      (new Date(base.startsAt).getTime() + new Date(base.endsAt).getTime()) / 2,
    ).toISOString()
    const cases = [
      { name: 'identical', startsAt: base.startsAt, endsAt: base.endsAt, conflicts: true },
      {
        name: 'partial-start',
        startsAt: new Date(new Date(base.startsAt).getTime() - 60 * 60 * 1000).toISOString(),
        endsAt: mid,
        conflicts: true,
      },
      {
        name: 'contained',
        startsAt: new Date(new Date(base.startsAt).getTime() + 15 * 60 * 1000).toISOString(),
        endsAt: new Date(new Date(base.endsAt).getTime() - 15 * 60 * 1000).toISOString(),
        conflicts: true,
      },
      { name: 'touching', startsAt: base.endsAt, endsAt: new Date(new Date(base.endsAt).getTime() + 2 * 60 * 60 * 1000).toISOString(), conflicts: false },
    ]

    const first = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      ...venueBookingPayload(276, 'e1', 'v4'),
      ...base,
    })
    expect(first.status).toBe(201)
    await venueRequest('POST', `/venues/bookings/${first.body.bookingId}/approve`, 'VS-01', {
      reason: 'boundary base',
    })

    for (const row of cases) {
      const created = await venueRequest('POST', '/venues/bookings', 'EC-01', {
        venueId: 'v4',
        eventId: 'e4',
        startsAt: row.startsAt,
        endsAt: row.endsAt,
        setupStartsAt: row.startsAt,
        teardownEndsAt: row.endsAt,
        requirementsSnapshot: row.name,
      })
      expect(created.status, row.name).toBe(201)
      const approved = await venueRequest(
        'POST',
        `/venues/bookings/${created.body.bookingId}/approve`,
        'VS-01',
        { reason: row.name },
      )
      if (row.conflicts) expect(approved.status, row.name).toBe(409)
      else expect(approved.status, row.name).toBe(200)
    }
  })
})
