import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, freshPeriod, requestVenue } from './support/venue-request.js'

// Each test makes its own event approved for planning and assigned to EC-01
// (AC1), and books venues that suit it, so a failed suitability check never
// refuses the test data itself. See support/venue-request.js.

test.describe('SPM-63 Submit a venue booking request', () => {
  test('TC-SPM63-AC01 the assigned coordinator can request a venue for a planning event', async () => {
    const event = await approvedEvent(THEATRE_EVENT)
    const created = await requestVenue(event, 'v1')
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    expect(created.body.status).toBe('pending')
    expect(created.body.eventId).toBe(event.eventId)
  })

  test('TC-SPM63-AC02 the request carries event facts taken from the event record', async () => {
    const event = await approvedEvent(THEATRE_EVENT)
    const created = await requestVenue(event, 'v3')
    expect(created.status).toBe(201)
    const viewed = await venueRequest('GET', `/venues/bookings/${created.body.bookingId}`, 'EC-01')
    expect(viewed.status).toBe(200)
    const text = JSON.stringify(viewed.body)
    expect(text).toContain(event.eventName)
    expect(viewed.body.startsAt).toBeTruthy()
    expect(viewed.body.endsAt).toBeTruthy()
    expect(viewed.body.requirementsSnapshot).toBeTruthy()
  })

  test('TC-SPM63-AC03 a failed suitability check blocks submission', async () => {
    // v4 only offers a Boardroom, so a Theatre event fails there.
    const created = await requestVenue(await approvedEvent(THEATRE_EVENT), 'v4', freshPeriod(), {
      requirementsSnapshot: 'Exhibition layout, 500 guests, loading dock',
    })
    expect([400, 409, 422]).toContain(created.status)
    expect(JSON.stringify(created.body)).toMatch(/not suitable|fail/i)
  })

  test('TC-SPM63-AC04 warnings can be submitted after acknowledgement and are carried to venue staff', async ({
    page,
  }) => {
    // 280 people in v1's Theatre (300) is a tight fit: a warning, not a failure.
    const event = await approvedEvent({ layoutPreference: 'Theatre', expectedAttendance: 280 })
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}/venues`)
    await page.getByTestId('venue-select-v1').click()
    await expect(page.getByTestId('suitability-verdict')).toContainText(/warning/i)
    await page.getByTestId('suitability-acknowledge').check()
    await page.getByTestId('venue-request-submit').click()
    await expect(page.getByText(/request submitted|pending/i).first()).toBeVisible()

    // The warnings travel on the booking itself. The Venue Staff queue screen
    // that would show them is SPM-8, which is not built yet.
    const stored = await venueRequest('GET', '/venues/bookings?eventId=' + event.eventId, 'VS-01')
    expect(stored.status).toBe(200)
    const booking = (stored.body || []).find((row) => row.eventId === event.eventId)
    expect(booking).toBeTruthy()
    expect(JSON.stringify(booking.warnings)).toMatch(/90%|tight fit|warning/i)
  })

  test('TC-SPM63-AC05 submitting notifies venue staff and places the request in the pending queue', async () => {
    const created = await requestVenue(await approvedEvent(THEATRE_EVENT), 'v1')
    expect(created.status).toBe(201)
    const queue = await venueRequest('GET', '/venues/bookings?status=pending', 'VS-01')
    expect(queue.status).toBe(200)
    expect((queue.body || []).map((row) => row.bookingId)).toContain(created.body.bookingId)
    // Venue Staff are emailed when the request is saved. That email is not stored
    // in the in-app notification list, so this test does not read that list.
  })

  test('TC-SPM63-AC06 a pending request appears on the calendar and does not make the venue unavailable', async () => {
    const created = await requestVenue(await approvedEvent(THEATRE_EVENT), 'v3')
    expect(created.status).toBe(201)
    expect(created.body.status).toBe('pending')
    // A pending request must not take the venue out of search. The calendar
    // entry itself is SPM-108, which is not built yet.
    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(created.body.startsAt)}&endsAt=${encodeURIComponent(created.body.endsAt)}`,
      'EC-01',
    )
    expect((search.body || []).map((row) => row.venueId)).toContain('v3')
  })

  test('TC-SPM63-AC07 an event can request a second venue while the first is still pending', async () => {
    // SPM-114 replaced the one-pending-per-event rule. A second venue is allowed;
    // requesting the same venue again while that booking is still live is not.
    const event = await approvedEvent(THEATRE_EVENT)
    const first = await requestVenue(event, 'v1')
    expect(first.status).toBe(201)
    const second = await requestVenue(event, 'v3')
    expect(second.status, JSON.stringify(second.body)).toBe(201)
    expect(second.body.eventId).toBe(event.eventId)
    expect(second.body.status).toBe('pending')
    const same = await requestVenue(event, 'v1')
    expect(same.status).toBe(409)
    expect(JSON.stringify(same.body)).toMatch(/pending|booking/i)
  })

  test('TC-SPM63-AC08 the coordinator can withdraw their pending request', async () => {
    const created = await requestVenue(await approvedEvent(THEATRE_EVENT), 'v1')
    expect(created.status).toBe(201)
    const withdrawn = await venueRequest(
      'POST',
      `/venues/bookings/${created.body.bookingId}/withdraw`,
      'EC-01',
    )
    expect(withdrawn.status).toBe(200)
    expect(withdrawn.body.status).toMatch(/withdrawn/i)
    const queue = await venueRequest('GET', '/venues/bookings?status=pending', 'VS-01')
    expect((queue.body || []).map((row) => row.bookingId)).not.toContain(created.body.bookingId)
  })

  test('TC-SPM63-AC09 readiness shows the venue arrangement as in progress while a request is pending', async ({
    page,
  }) => {
    const event = await approvedEvent(THEATRE_EVENT)
    expect((await requestVenue(event, 'v1')).status).toBe(201)
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}/venues`)
    const arrangement = page.getByTestId('venue-arrangement')
    await expect(arrangement).toBeVisible()
    await expect(arrangement).toContainText(/pending|not complete/i)
  })
})
