import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { eventApi } from './support/event.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './support/venue-request.js'

// SPM-115. Venue Staff record a block. The assigned coordinator searches for
// another venue and requests it. The original booking stays readable, and the
// event's own details are left as they were.

async function eventRecord(eventId) {
  const read = await eventApi('GET', `/${eventId}`, 'EC-01')
  expect(read.status, JSON.stringify(read.body)).toBe(200)
  return read.body
}

function facts(event) {
  return {
    status: event.status,
    eventName: event.eventName,
    expectedAttendance: event.expectedAttendance,
    layoutPreference: event.layoutPreference,
    proposedStartAt: event.proposedStartAt,
    proposedEndAt: event.proposedEndAt,
  }
}

async function approvedBooking(event, venueId) {
  const created = await requestVenue(event, venueId)
  expect(created.status, JSON.stringify(created.body)).toBe(201)
  const approved = await venueRequest('POST', `/venues/bookings/${created.body.bookingId}/approve`, 'VS-01', {
    reason: 'Booked',
  })
  expect(approved.status, JSON.stringify(approved.body)).toBe(200)
  return approved.body
}

async function blockVenue(venueId, booking) {
  return venueRequest('POST', `/venues/${venueId}/unavailability`, 'VS-01', {
    startsAt: booking.startsAt,
    endsAt: booking.endsAt,
    reason: 'maintenance',
    acknowledgeConflicts: true,
  })
}

test.describe('SPM-115 Request a replacement venue', () => {
  test('TC-SPM115-AC01 the assigned coordinator can search for and request a replacement', async ({ page }) => {
    const event = await approvedEvent(THEATRE_EVENT)
    const booking = await approvedBooking(event, 'v1')
    const blocked = await blockVenue('v1', booking)
    expect(blocked.status, JSON.stringify(blocked.body)).toBe(201)

    const search = await venueRequest(
      'GET',
      `/venues/search?eventId=${event.eventId}&startsAt=${encodeURIComponent(booking.startsAt)}&endsAt=${encodeURIComponent(booking.endsAt)}&layout=Theatre&minCapacity=50`,
      'EC-01',
    )
    expect(search.status).toBe(200)
    const ids = (search.body || []).map((row) => row.venueId)
    expect(ids).not.toContain('v1')
    expect(ids).toContain('v3')

    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}/venues`)
    await page.getByTestId('venue-replacement-open').click()
    await page.getByTestId('venue-replacement-search').click()
    await page.getByTestId('venue-replacement-v3').click()
    await expect(page.getByTestId('venue-request-result')).toContainText(/replacement requested/i)
    await expect(page.getByText(/cancelled/i).first()).toBeVisible()
  })

  test('TC-SPM115-AC02 the replacement is checked on its own', async () => {
    const event = await approvedEvent(THEATRE_EVENT)
    const booking = await approvedBooking(event, 'v1')
    expect((await blockVenue('v1', booking)).status).toBe(201)

    const unsuitable = await venueRequest('POST', `/venues/bookings/${booking.bookingId}/replacement`, 'EC-01', {
      venueId: 'v4',
    })
    expect(unsuitable.status).toBe(409)
    expect(JSON.stringify(unsuitable.body)).toMatch(/not suitable/i)
    const kept = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'EC-01')
    expect(kept.body.status).toBe('approved')

    const other = await approvedEvent(THEATRE_EVENT)
    const created = await requestVenue(other, 'v3', { startsAt: booking.startsAt, endsAt: booking.endsAt })
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    const occupying = await venueRequest('POST', `/venues/bookings/${created.body.bookingId}/approve`, 'VS-01', {
      reason: 'Already booked',
    })
    expect(occupying.status, JSON.stringify(occupying.body)).toBe(200)
    const clash = await venueRequest('POST', `/venues/bookings/${booking.bookingId}/replacement`, 'EC-01', {
      venueId: 'v3',
    })
    expect(clash.status, JSON.stringify(clash.body)).toBe(409)
    expect(occupying.body.status).toBe('approved')
  })

  test('TC-SPM115-AC03 the original booking remains readable', async () => {
    const event = await approvedEvent(THEATRE_EVENT)
    const booking = await approvedBooking(event, 'v1')
    expect((await blockVenue('v1', booking)).status).toBe(201)
    const created = await venueRequest('POST', `/venues/bookings/${booking.bookingId}/replacement`, 'EC-01', {
      venueId: 'v3',
    })
    expect(created.status, JSON.stringify(created.body)).toBe(201)

    const original = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'EC-01')
    expect(original.status).toBe(200)
    expect(original.body.status).toBe('cancelled')
    expect(original.body.venueId).toBe('v1')
    expect(original.body.startsAt).toBe(booking.startsAt)
    expect(original.body.endsAt).toBe(booking.endsAt)
    expect(original.body.eventId).toBe(event.eventId)
  })

  test('TC-SPM115-AC04 the event details stay unchanged', async () => {
    const event = await approvedEvent(THEATRE_EVENT)
    const before = facts(await eventRecord(event.eventId))
    const booking = await approvedBooking(event, 'v1')
    expect((await blockVenue('v1', booking)).status).toBe(201)
    const created = await venueRequest('POST', `/venues/bookings/${booking.bookingId}/replacement`, 'EC-01', {
      venueId: 'v3',
    })
    expect(created.status).toBe(201)
    expect(created.body.startsAt).toBe(booking.startsAt)
    expect(created.body.endsAt).toBe(booking.endsAt)

    expect(facts(await eventRecord(event.eventId))).toEqual(before)
  })

  test('TC-SPM115-AC05 recording the block leaves the event status unchanged', async () => {
    const event = await approvedEvent(THEATRE_EVENT)
    const before = await eventRecord(event.eventId)
    const booking = await approvedBooking(event, 'v1')
    const refused = await venueRequest('POST', '/venues/v1/unavailability', 'VS-01', {
      startsAt: booking.startsAt,
      endsAt: booking.endsAt,
      reason: 'maintenance',
    })
    expect(refused.status).toBe(409)
    expect((await eventRecord(event.eventId)).status).toBe(before.status)
    expect((await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')).body.status).toBe('approved')

    const saved = await blockVenue('v1', booking)
    expect(saved.status, JSON.stringify(saved.body)).toBe(201)
    const after = await eventRecord(event.eventId)
    expect(after.status).toBe(before.status)
    expect(facts(after)).toEqual(facts(before))
    expect((await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')).body.status).toBe('approved')
  })
})
