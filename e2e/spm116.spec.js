import { test, expect } from '@playwright/test'
import { newVenuePayload } from './support/api-data.js'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { notificationRequest, venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, freshPeriod, requestVenue } from './support/venue-request.js'

// The suite makes its own hall (30 minutes setup, 45 minutes turnaround, open every
// day) and retires it afterwards, so seeded venues are never held. Each test sends
// its own requests on a random day years ahead: a 10:00 to 12:00 event occupies
// the hall from 09:30 to 12:45. All times are UTC.

const MINUTE = 60 * 1000
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const HALL_EVENT = { ...THEATRE_EVENT, venueRequirements: 'Projector.', accessibilityNeeds: 'None.' }

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

async function pending(period) {
  const event = await approvedEvent(HALL_EVENT)
  const sent = await requestVenue(event, hall.venueId, period, { acknowledgeWarnings: true })
  expect(sent.status, JSON.stringify(sent.body)).toBe(201)
  return { event, booking: sent.body }
}

function hold(booking, expiresAt, accountId = 'VS-01') {
  return venueRequest('POST', `/venues/bookings/${booking.bookingId}/hold`, accountId, { expiresAt })
}

function approve(booking) {
  return venueRequest('POST', `/venues/bookings/${booking.bookingId}/approve`, 'VS-01', { reason: 'SPM-116 test' })
}

async function hallListed(period) {
  const query = `startsAt=${encodeURIComponent(period.startsAt)}&endsAt=${encodeURIComponent(period.endsAt)}`
  const search = await venueRequest('GET', `/venues/search?${query}`, 'EC-01')
  expect(search.status, JSON.stringify(search.body)).toBe(200)
  return search.body.some((row) => row.venueId === hall.venueId)
}

// A day before the event: in the future, and before the event starts.
const dayBefore = (base) => shift(base.startsAt, -24 * 60)

test.describe('SPM-116 Place a tentative hold with an expiry', () => {
  test.beforeAll(async () => {
    const created = await venueRequest('POST', '/venues', 'VS-01', {
      ...newVenuePayload(`AUTO-SPM116 Hall ${Date.now()}`),
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

  test('TC-SPM116-AC01 venue staff hold a pending request until a future time no later than the event start', async () => {
    const base = freshPeriod()
    const a = await pending(base)

    // Negative: a time already past, and one minute after the event starts.
    const past = await hold(a.booking, new Date(Date.now() - MINUTE).toISOString())
    expect([past.status, past.body.detail]).toEqual([422, 'The hold must expire at a future date and time.'])
    const late = await hold(a.booking, shift(base.startsAt, 1))
    expect(late.status).toBe(422)
    expect(late.body.detail).toMatch(/^The hold must expire no later than the event's start/)

    // Boundary: exactly the event's start is accepted.
    const held = await hold(a.booking, base.startsAt)
    expect(held.status, JSON.stringify(held.body)).toBe(200)
    expect(held.body.status).toBe('pending')
    expect(held.body.hold).toMatchObject({ state: 'active', placedBy: 'u3' })
    expect(utc(held.body.hold.expiresAt)).toBe(base.startsAt)

    // Negative: holding it again, or holding a request that is no longer pending.
    const again = await hold(a.booking, dayBefore(base))
    expect(again.status).toBe(409)
    expect(again.body.detail).toMatch(/^This request is already held until .* Release that hold first/)
    const other = await pending(slot(base, 480, 540)) // 18:00 to 19:00, clear of A
    expect((await approve(other.booking)).status).toBe(200)
    const notPending = await hold(other.booking, dayBefore(base))
    expect([notPending.status, notPending.body.detail]).toEqual([
      409,
      'Only a pending booking request can be held. This request is already approved.',
    ])
  })

  test('TC-SPM116-AC01b venue staff place and release a hold from the venue catalogue', async ({ page }) => {
    const base = freshPeriod()
    const { booking } = await pending(base)
    const until = dayBefore(base).slice(0, 16) // datetime-local, read as UTC

    await login(page, account('VS-01'))
    await page.locator('.nav-item').getByText('Venue Catalogue', { exact: true }).click()
    await page.getByText(hall.name, { exact: true }).click()
    await expect(page.getByTestId(`venue-hold-request-${booking.bookingId}`)).toBeVisible()

    await page.getByTestId(`venue-hold-until-${booking.bookingId}`).fill(until)
    await page.getByTestId(`venue-hold-place-${booking.bookingId}`).click()
    await expect(page.getByTestId(`venue-hold-state-${booking.bookingId}`)).toContainText('Held until')

    await page.getByTestId(`venue-hold-release-${booking.bookingId}`).click()
    await expect(page.getByTestId(`venue-hold-place-${booking.bookingId}`)).toBeVisible()
    const after = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')
    expect(after.body.hold.state).toBe('released')
  })

  test('TC-SPM116-AC02 an active hold reserves the venue for its occupied window', async () => {
    const base = freshPeriod()
    const a = await pending(base) // 10:00 to 12:00, occupies 09:30 to 12:45
    const b = await pending(slot(base, 120, 180)) // 12:00 to 13:00, set up from 11:30
    expect((await hold(a.booking, dayBefore(base))).status).toBe(200)

    expect(await hallListed(slot(base, 120, 180))).toBe(false)
    expect(await hallListed(slot(base, 195, 240))).toBe(true) // 13:15, set up from 12:45: only touches
    const check = await venueRequest('POST', '/venues/suitability', 'EC-01', {
      eventId: b.event.eventId,
      venueId: hall.venueId,
      ...slot(base, 120, 180),
    })
    expect(check.body.verdict).toBe('not suitable')
    expect(JSON.stringify(check.body.reasons)).toContain(`is on a tentative hold for \\"${a.event.eventName}\\"`)

    const refused = await approve(b.booking)
    expect(refused.status).toBe(409)
    expect(refused.body.detail).toMatch(/is on a tentative hold until .* so this request cannot be approved\./)
    const newcomer = await requestVenue(await approvedEvent(HALL_EVENT), hall.venueId, slot(base, 120, 180), {
      acknowledgeWarnings: true,
    })
    expect(newcomer.status).toBe(409)

    // The held request itself can be approved; its hold becomes the booking.
    const approved = await approve(a.booking)
    expect(approved.status, JSON.stringify(approved.body)).toBe(200)
    expect(approved.body.hold.state).toBe('approved')
  })

  test('TC-SPM116-AC02b releasing a hold frees the venue', async () => {
    const base = freshPeriod()
    const a = await pending(base)
    const b = await pending(slot(base, 120, 180))
    expect((await hold(a.booking, dayBefore(base))).status).toBe(200)

    const released = await venueRequest('POST', `/venues/bookings/${a.booking.bookingId}/hold/release`, 'VS-01')
    expect([released.status, released.body.hold.state]).toEqual([200, 'released'])
    expect(await hallListed(slot(base, 120, 180))).toBe(true)
    expect((await approve(b.booking)).status).toBe(200)

    const twice = await venueRequest('POST', `/venues/bookings/${a.booking.bookingId}/hold/release`, 'VS-01')
    expect([twice.status, twice.body.detail]).toEqual([409, 'This request has no active hold to release.'])
  })

  test('TC-SPM116-AC03 and AC04 an expired hold reserves nothing and is not a confirmed booking', async () => {
    test.setTimeout(180_000)
    const base = freshPeriod()
    const a = await pending(base)
    const b = await pending(slot(base, 120, 180))
    const soon = new Date(Date.now() + 65 * 1000).toISOString()
    expect((await hold(a.booking, soon)).status).toBe(200)
    expect(await hallListed(slot(base, 120, 180))).toBe(false)

    // Let the hold run out on its own; nothing releases it.
    await new Promise((done) => setTimeout(done, 70 * 1000))

    const expired = await venueRequest('GET', `/venues/bookings/${a.booking.bookingId}`, 'VS-01')
    expect([expired.body.status, expired.body.hold.state]).toEqual(['pending', 'expired'])
    expect(await hallListed(slot(base, 120, 180))).toBe(true)
    expect((await approve(b.booking)).status).toBe(200)
  })

  test('TC-SPM116-AC05 the assigned coordinator is told until when the venue is held', async ({ page }) => {
    const base = freshPeriod()
    const { event, booking } = await pending(base)
    expect((await hold(booking, dayBefore(base))).status).toBe(200)

    const inbox = await notificationRequest('/notifications', 'EC-01')
    expect(inbox.status).toBe(200)
    const notice = inbox.body.find((row) => row.type === 'venue.hold' && row.eventId === event.eventId)
    expect(notice, JSON.stringify(inbox.body.slice(0, 3))).toBeTruthy()
    expect(notice.title).toBe('Venue on hold for your event')
    expect(notice.body).toContain(`${hall.name} is on a tentative hold for "${event.eventName}" until`)
    expect(notice.body).toContain('the hold expires and the venue becomes available to other requests')

    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}/venues`)
    await expect(page.getByTestId(`venue-hold-${booking.bookingId}`)).toContainText('Held until')
  })

  test('TC-SPM116-AC06 rejecting a booking request releases its hold', async () => {
    const base = freshPeriod()
    const a = await pending(base)
    const b = await pending(slot(base, 120, 180))
    expect((await hold(a.booking, dayBefore(base))).status).toBe(200)

    const rejected = await venueRequest('POST', `/venues/bookings/${a.booking.bookingId}/reject`, 'VS-01', {
      reason: 'SPM-116 test',
    })
    expect([rejected.status, rejected.body.status, rejected.body.hold.state]).toEqual([200, 'rejected', 'rejected'])
    expect(await hallListed(slot(base, 120, 180))).toBe(true)
    expect((await approve(b.booking)).status).toBe(200)
  })

  test('TC-SPM116-AC01c only venue staff can hold or release', async () => {
    const base = freshPeriod()
    const { booking } = await pending(base)

    expect((await hold(booking, dayBefore(base), 'EC-01')).status).toBe(403)
    const release = await venueRequest('POST', `/venues/bookings/${booking.bookingId}/hold/release`, 'EC-01')
    expect(release.status).toBe(403)
  })
})
