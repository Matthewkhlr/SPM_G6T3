import { test, expect } from '@playwright/test'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, freshPeriod, requestVenue } from './support/venue-request.js'

// Seeded Marina Hall A (v1) has 30 minutes setup and 60 minutes turnaround, so a
// 10:00 to 12:00 booking occupies it from 09:30 to 13:00. Every test uses its own
// events on a random day years ahead, so runs never meet each other's bookings.

const MINUTE = 60 * 1000

function shift(iso, minutes) {
  return new Date(new Date(iso).getTime() + minutes * MINUTE).toISOString()
}

// The server returns UTC times without a zone marker.
function utc(value) {
  return new Date(/Z|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`).toISOString()
}

function slot(base, fromMinutes, toMinutes) {
  return { startsAt: shift(base.startsAt, fromMinutes), endsAt: shift(base.startsAt, toMinutes) }
}

// A pending request for a new event approved for planning. Later requests at an
// overlapping time carry a warning about the earlier one, so they acknowledge it.
async function pending(period, venueId = 'v1') {
  const event = await approvedEvent(THEATRE_EVENT)
  const sent = await requestVenue(event, venueId, period, { acknowledgeWarnings: true })
  expect(sent.status, JSON.stringify(sent.body)).toBe(201)
  return { event, booking: sent.body }
}

function approve(booking) {
  return venueRequest('POST', `/venues/bookings/${booking.bookingId}/approve`, 'VS-01', { reason: 'SPM-64 test' })
}

test.describe('SPM-64 Prevent double-booking of a venue', () => {
  test('TC-SPM64-AC01 search, suitability, and approval apply the same rule', async () => {
    const base = freshPeriod()
    const first = await pending(base)
    const second = await pending(slot(base, 150, 240)) // 12:30 to 14:00
    expect((await approve(first.booking)).status).toBe(200)

    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(shift(base.startsAt, 150))}&endsAt=${encodeURIComponent(shift(base.startsAt, 240))}`,
      'EC-01',
    )
    const suitability = await venueRequest('POST', '/venues/suitability', 'EC-01', {
      eventId: second.event.eventId,
      venueId: 'v1',
      ...slot(base, 150, 240),
    })
    const approval = await approve(second.booking)

    expect(search.status).toBe(200)
    expect(search.body.map((row) => row.venueId)).not.toContain('v1')
    expect(suitability.body.verdict).toBe('not suitable')
    expect(approval.status).toBe(409)
  })

  test('TC-SPM64-AC02 the occupied window adds the venue setup and turnaround time', async () => {
    const base = freshPeriod()
    const { booking } = await pending(base)

    expect(utc(booking.setupStartsAt)).toBe(shift(base.startsAt, -30))
    expect(utc(booking.teardownEndsAt)).toBe(shift(base.endsAt, 60))
  })

  test('TC-SPM64-AC03 a second overlapping booking cannot be confirmed and the clash is named', async () => {
    const base = freshPeriod()
    const first = await pending(base)
    const second = await pending(slot(base, 60, 180))
    expect((await approve(first.booking)).status).toBe(200)

    const refused = await approve(second.booking)

    expect(refused.status).toBe(409)
    expect(refused.body.detail).toContain(`Marina Hall A is already confirmed for "${first.event.eventName}"`)
    // The database refusing an overlap on its own is proven in
    // services/venue-service/tests/integration/test_double_booking_mysql.py.
  })

  test('TC-SPM64-AC04 a confirmed booking conflicts with unavailability and with an active hold', async () => {
    test.skip(
      true,
      'Recording unavailability is SPM-9 and tentative holds are SPM-116, neither built yet. The unavailability rule is unit-tested in test_venue_double_booking.py.',
    )
  })

  test('TC-SPM64-AC05 an expired tentative hold does not conflict', async () => {
    test.skip(true, 'Tentative holds are SPM-116, not built yet; remove this skip when it ships.')
  })

  test('TC-SPM64-AC06 touching windows are fine, touching event times can still clash', async () => {
    const base = freshPeriod()
    const first = await pending(base)
    const touchingWindow = await pending(slot(base, 210, 240)) // 13:30 to 14:00, set up from 13:00
    const touchingTimes = await pending(slot(base, 120, 180)) // 12:00 to 13:00, set up from 11:30
    expect((await approve(first.booking)).status).toBe(200)

    expect((await approve(touchingWindow.booking)).status).toBe(200)
    expect((await approve(touchingTimes.booking)).status).toBe(409)
  })

  test('TC-SPM64-AC07 two approvals for clashing requests at once: exactly one succeeds', async () => {
    const base = freshPeriod()
    const a = await pending(base)
    const b = await pending(slot(base, 30, 150))

    const results = await Promise.all([approve(a.booking), approve(b.booking)])

    expect(results.map((result) => result.status).sort()).toEqual([200, 409])
    expect(results.find((result) => result.status === 409).body.detail).toMatch(/cannot be approved/)
  })

  test('TC-SPM64-AC08 withdrawing, cancelling a booking, or cancelling the event frees the venue', async () => {
    // Withdrawing (SPM-63) a pending request.
    const base = freshPeriod()
    const first = await pending(base)
    const withdrawn = await venueRequest('POST', `/venues/bookings/${first.booking.bookingId}/withdraw`, 'EC-01')
    expect(withdrawn.status, JSON.stringify(withdrawn.body)).toBe(200)
    const second = await pending(base)
    expect((await approve(second.booking)).status).toBe(200)

    // Cancelling that one confirmed booking (SPM-114) frees the period.
    const cancelled = await venueRequest('POST', `/venues/bookings/${second.booking.bookingId}/cancel`, 'VS-01')
    expect(cancelled.status, JSON.stringify(cancelled.body)).toBe(200)
    const third = await pending(base)
    expect((await approve(third.booking)).status).toBe(200)

    // Cancelling the event releases all its bookings (SPM-114's release, which
    // event cancellation in SPM-88 is to call).
    const released = await venueRequest('POST', '/venues/bookings/release', 'EC-01', { eventId: third.event.eventId })
    expect(released.status, JSON.stringify(released.body)).toBe(200)
    expect(released.body.map((row) => row.status)).toEqual(['cancelled'])
    const fourth = await pending(base)
    expect((await approve(fourth.booking)).status).toBe(200)
  })
})
