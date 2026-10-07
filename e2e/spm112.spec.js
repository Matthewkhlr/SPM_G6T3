import { test, expect } from '@playwright/test'
import { newVenuePayload } from './support/api-data.js'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, freshPeriod, requestVenue } from './support/venue-request.js'

// The customer's example venue: 30 minutes setup and 45 minutes turnaround, open
// every day, so a 10:00 to 12:00 booking occupies it from 09:30 to 12:45. The
// suite makes its own venue and retires it afterwards, so seeded venues are
// never edited. Every test uses its own events on a random day years ahead.

const MINUTE = 60 * 1000
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

let hall

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

function windowOf(booking) {
  return [utc(booking.setupStartsAt), utc(booking.teardownEndsAt)]
}

async function pending(period) {
  const event = await approvedEvent(THEATRE_EVENT)
  const sent = await requestVenue(event, hall.venueId, period, { acknowledgeWarnings: true })
  expect(sent.status, JSON.stringify(sent.body)).toBe(201)
  return { event, booking: sent.body }
}

function approve(booking) {
  return venueRequest('POST', `/venues/bookings/${booking.bookingId}/approve`, 'VS-01', { reason: 'SPM-112 test' })
}

// A request sent while the hall is still free, and then, once another booking
// is confirmed, what search, suitability and approval each say about it. A new
// request at a clashing time is refused outright by the same check (SPM-63 AC3).
async function answers({ event, booking, period }) {
  const query = `startsAt=${encodeURIComponent(period.startsAt)}&endsAt=${encodeURIComponent(period.endsAt)}`
  const search = await venueRequest('GET', `/venues/search?${query}`, 'EC-01')
  const suitability = await venueRequest('POST', '/venues/suitability', 'EC-01', {
    eventId: event.eventId,
    venueId: hall.venueId,
    ...period,
  })
  const request = await requestVenue(await approvedEvent(THEATRE_EVENT), hall.venueId, period, {
    acknowledgeWarnings: true,
  })
  const approval = await approve(booking)
  expect(search.status, JSON.stringify(search.body)).toBe(200)
  expect(suitability.status, JSON.stringify(suitability.body)).toBe(200)
  return {
    searchExcludes: !search.body.some((row) => row.venueId === hall.venueId),
    // A pending request nearby only adds a warning (SPM-63 AC6); not suitable means a clash.
    suitabilityFails: suitability.body.verdict === 'not suitable',
    newRequest: request.status,
    approval: approval.status,
    reason: approval.body.detail,
  }
}

async function candidate(period) {
  return { ...(await pending(period)), period }
}

const CLASH = { searchExcludes: true, suitabilityFails: true, newRequest: 409, approval: 409 }
const FREE = { searchExcludes: false, suitabilityFails: false, newRequest: 201, approval: 200 }

// For the screen test: requirements the hall meets, so only the time decides.
const HALL_EVENT = { ...THEATRE_EVENT, venueRequirements: 'Projector.', accessibilityNeeds: 'None.' }

// The coordinator's venue page (SPM-61 and SPM-62 screens) for an event at `period`:
// pick the hall, read its verdict, then search with the event's own requirements.
async function onTheVenueScreen(page, period) {
  const event = await approvedEvent({ ...HALL_EVENT, proposedStartAt: period.startsAt, proposedEndAt: period.endsAt })
  await page.goto(`/app/events/${event.eventId}/venues`)
  await page.getByTestId(`venue-select-${hall.venueId}`).click()
  const verdict = page.getByTestId('suitability-verdict')
  await expect(verdict).toBeVisible()
  const shown = { verdict: (await verdict.textContent()).trim() }
  await page.getByTestId('venue-search-submit').click()
  await expect(page.getByTestId('venue-search-summary')).toBeVisible()
  shown.listed = (await page.getByTestId(`venue-select-${hall.venueId}`).count()) === 1
  return shown
}

test.describe('SPM-112 Check availability using setup and turnaround', () => {
  test.beforeAll(async () => {
    const created = await venueRequest('POST', '/venues', 'VS-01', {
      ...newVenuePayload(`AUTO-SPM112 Hall ${Date.now()}`),
      layouts: [{ name: 'Theatre', capacity: 100 }],
      operatingHours: DAYS.map((day) => ({ day, opens: '00:00', closes: '24:00' })),
      setupMinutes: 30,
      turnaroundMinutes: 45,
    })
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    hall = created.body
  })

  test.afterAll(async () => {
    if (hall) await venueRequest('POST', `/venues/${hall.venueId}/retire?confirm=true`, 'VS-01')
  })

  test('TC-SPM112-AC01 the occupied window runs from start minus setup to end plus turnaround', async () => {
    const base = freshPeriod() // 10:00 to 12:00
    const { booking } = await pending(base)

    expect(windowOf(booking)).toEqual([shift(base.startsAt, -30), shift(base.endsAt, 45)]) // 09:30 to 12:45
    const shown = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')
    expect(shown.status, JSON.stringify(shown.body)).toBe(200)
    expect(windowOf(shown.body)).toEqual([shift(base.startsAt, -30), shift(base.endsAt, 45)])

    // The window follows the venue's current setup and turnaround times.
    const edited = await venueRequest('PATCH', `/venues/${hall.venueId}`, 'VS-01', {
      setupMinutes: 15,
      turnaroundMinutes: 60,
    })
    expect(edited.status, JSON.stringify(edited.body)).toBe(200)
    try {
      const after = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')
      expect(windowOf(after.body)).toEqual([shift(base.startsAt, -15), shift(base.endsAt, 60)]) // 09:45 to 13:00
    } finally {
      const restored = await venueRequest('PATCH', `/venues/${hall.venueId}`, 'VS-01', {
        setupMinutes: 30,
        turnaroundMinutes: 45,
      })
      expect(restored.status, JSON.stringify(restored.body)).toBe(200)
    }
  })

  test('TC-SPM112-AC02 search, suitability and approval use the same occupied window', async () => {
    const base = freshPeriod()
    const held = await pending(base)
    const inside = await candidate(slot(base, 150, 240)) // 12:30 to 14:00, set up from 12:00
    const clear = await candidate(slot(base, 210, 270)) // 13:30 to 14:30, set up from 13:00
    expect((await approve(held.booking)).status).toBe(200) // holds 09:30 to 12:45

    const clash = await answers(inside)
    expect(clash).toMatchObject(CLASH)
    expect(clash.reason).toContain('including setup and turnaround')
    expect(await answers(clear)).toMatchObject(FREE)
    // Recording unavailability (SPM-9), rescheduling (SPM-87) and re-verification
    // (SPM-86) are not built yet. The unavailability check inside the same rule
    // is unit-tested in services/venue-service/tests/unit/test_venue_occupied_window.py.
  })

  test('TC-SPM112-AC02b the coordinator venue screen applies the same window', async ({ page }) => {
    const base = freshPeriod()
    const held = await pending(base)
    expect((await approve(held.booking)).status).toBe(200) // holds 09:30 to 12:45
    await login(page, account('EC-01'))

    // 12:00 to 13:00 only touches the confirmed event, but its setup from 11:30 clashes.
    const clashing = await onTheVenueScreen(page, slot(base, 120, 180))
    expect(clashing).toEqual({ verdict: 'Not suitable', listed: false })
    await page.getByTestId('venue-search-reset').click()
    await page.getByTestId(`venue-select-${hall.venueId}`).click()
    await expect(page.getByTestId('suitability-reasons')).toContainText('including setup and turnaround')
    await expect(page.getByTestId('venue-request-submit')).toBeDisabled()

    // 13:15 to 14:00 is set up from 12:45, so its window only touches.
    const touching = await onTheVenueScreen(page, slot(base, 195, 240))
    expect(touching).toEqual({ verdict: 'Suitable', listed: true })
  })

  test('TC-SPM112-AC03 occupied windows that only touch do not conflict', async () => {
    const base = freshPeriod()
    const held = await pending(base)
    const after = await candidate(slot(base, 195, 240)) // 13:15 to 14:00, set up from 12:45
    const before = await candidate(slot(base, -180, -75)) // 07:00 to 08:45, turned around by 09:30
    expect((await approve(held.booking)).status).toBe(200) // holds 09:30 to 12:45

    expect(await answers(after)).toMatchObject(FREE)
    expect(await answers(before)).toMatchObject(FREE)
  })

  test('TC-SPM112-AC04 event times that only touch still conflict when setup or turnaround overlap', async () => {
    const base = freshPeriod()
    const held = await pending(base)
    const startsAsItEnds = await candidate(slot(base, 120, 180)) // 12:00 to 13:00, set up from 11:30
    const endsAsItStarts = await candidate(slot(base, -120, 0)) // 08:00 to 10:00, turned around until 10:45
    expect((await approve(held.booking)).status).toBe(200) // holds 09:30 to 12:45

    expect(await answers(startsAsItEnds)).toMatchObject(CLASH)
    expect(await answers(endsAsItStarts)).toMatchObject(CLASH)
  })
})
