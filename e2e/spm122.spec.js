import { test, expect } from '@playwright/test'
import { newVenuePayload } from './support/api-data.js'
import { login } from './support/auth.js'
import { eventApi } from './support/event.js'
import { account } from './support/test-data.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, freshPeriod, requestVenue } from './support/venue-request.js'

// The suite makes its own hall with no setup or turnaround and confirms four
// bookings whose event times only touch, which is allowed then. Venue Staff then
// apply the customer's 30 minutes of setup and 45 minutes of turnaround. Seeded
// venues are never edited, and the hall is retired afterwards.
//   A 10:00-12:00 -> 09:30-12:45    B 12:00-13:00 -> 11:30-13:45
//   C 13:00-14:00 -> 12:30-14:45    D 15:15-16:00 -> 14:45-16:45 (touches C)

test.describe.configure({ mode: 'serial' })

const MINUTE = 60 * 1000
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const HALL_EVENT = { ...THEATRE_EVENT, venueRequirements: 'Projector.', accessibilityNeeds: 'None.' }

let hall
let base
const booked = {}

function shift(iso, minutes) {
  return new Date(new Date(iso).getTime() + minutes * MINUTE).toISOString()
}

// The server returns UTC times without a zone marker.
function utc(value) {
  return new Date(/Z|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`).toISOString()
}

function setTimes(setupMinutes, turnaroundMinutes) {
  return venueRequest('PATCH', `/venues/${hall.venueId}`, 'VS-01', { setupMinutes, turnaroundMinutes })
}

async function clashes() {
  const listed = await venueRequest('GET', `/venues/bookings/clashes?venueId=${hall.venueId}`, 'VS-01')
  expect(listed.status, JSON.stringify(listed.body)).toBe(200)
  return listed.body
}

const label = (bookingId) => Object.keys(booked).find((key) => booked[key].booking.bookingId === bookingId)
const pairs = (rows) => rows.map((row) => [label(row.first.bookingId), label(row.second.bookingId)])

test.describe('SPM-122 Flag bookings that clash under the new window', () => {
  test.beforeAll(async () => {
    test.setTimeout(180_000)
    const created = await venueRequest('POST', '/venues', 'VS-01', {
      ...newVenuePayload(`AUTO-SPM122 Hall ${Date.now()}`),
      layouts: [{ name: 'Theatre', capacity: 100 }],
      operatingHours: DAYS.map((day) => ({ day, opens: '00:00', closes: '24:00' })),
      setupMinutes: 0,
      turnaroundMinutes: 0,
    })
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    hall = created.body
    base = freshPeriod() // 10:00 to 12:00
    for (const [key, from, to] of [['A', 0, 120], ['B', 120, 180], ['C', 180, 240], ['D', 315, 360]]) {
      const event = await approvedEvent(HALL_EVENT)
      const period = { startsAt: shift(base.startsAt, from), endsAt: shift(base.startsAt, to) }
      const sent = await requestVenue(event, hall.venueId, period, { acknowledgeWarnings: true })
      expect(sent.status, JSON.stringify(sent.body)).toBe(201)
      const approved = await venueRequest('POST', `/venues/bookings/${sent.body.bookingId}/approve`, 'VS-01', {
        reason: 'SPM-122 test',
      })
      expect(approved.status, JSON.stringify(approved.body)).toBe(200)
      // The event as a normal read returns it, before any setup or turnaround is applied.
      const record = await eventApi('GET', `/${event.eventId}`, 'EC-01')
      expect(record.status, JSON.stringify(record.body)).toBe(200)
      booked[key] = { event, record: record.body, booking: approved.body }
    }
  })

  test.afterAll(async () => {
    if (hall) await venueRequest('POST', `/venues/${hall.venueId}/retire?confirm=true`, 'VS-01')
  })

  test('TC-SPM122-AC01 every pair whose occupied windows overlap is listed once setup and turnaround apply', async () => {
    expect(await clashes()).toEqual([])

    const applied = await setTimes(30, 45)
    expect(applied.status, JSON.stringify(applied.body)).toBe(200)

    // A and C are not neighbours, but A's turnaround reaches into C's setup.
    // C and D only touch, so they are not listed.
    expect(pairs(await clashes())).toEqual([['A', 'B'], ['A', 'C'], ['B', 'C']])
  })

  test('TC-SPM122-AC02 each clash names the venue, both events, and the overlapping times', async () => {
    const [first] = await clashes()

    expect(first.venueId).toBe(hall.venueId)
    expect(first.venueName).toBe(hall.name)
    expect([first.setupMinutes, first.turnaroundMinutes]).toEqual([30, 45])
    expect([first.first.eventId, first.first.eventName]).toEqual([booked.A.event.eventId, booked.A.event.eventName])
    expect([first.second.eventId, first.second.eventName]).toEqual([booked.B.event.eventId, booked.B.event.eventName])
    expect([utc(first.first.setupStartsAt), utc(first.first.teardownEndsAt)]).toEqual([
      shift(base.startsAt, -30),
      shift(base.startsAt, 165),
    ]) // 09:30 to 12:45
    expect([utc(first.second.setupStartsAt), utc(first.second.teardownEndsAt)]).toEqual([
      shift(base.startsAt, 90),
      shift(base.startsAt, 225),
    ]) // 11:30 to 13:45
    expect([utc(first.overlapStartsAt), utc(first.overlapEndsAt)]).toEqual([
      shift(base.startsAt, 90),
      shift(base.startsAt, 165),
    ]) // 11:30 to 12:45
  })

  test('TC-SPM122-AC03 listed bookings are kept with their status and event details', async () => {
    await clashes()

    for (const { booking } of Object.values(booked)) {
      const now = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')
      expect(now.status, JSON.stringify(now.body)).toBe(200)
      const kept = ['status', 'eventId', 'venueId', 'startsAt', 'endsAt', 'eventSnapshot', 'reviewedBy', 'reviewedAt']
      for (const field of kept) expect(now.body[field], field).toEqual(booking[field])
      expect(now.body.status).toBe('approved')
    }
  })

  test('TC-SPM122-AC04 the event records for those bookings stay unchanged', async () => {
    await clashes()

    for (const { event, record } of Object.values(booked)) {
      const now = await eventApi('GET', `/${event.eventId}`, 'EC-01')
      expect(now.status, JSON.stringify(now.body)).toBe(200)
      expect(now.body).toEqual(record)
    }
  })

  test('TC-SPM122-AC01b Venue Staff see the clashes in the catalogue as soon as they save new times', async ({
    page,
  }) => {
    expect((await setTimes(0, 0)).status).toBe(200)
    await login(page, account('VS-01'))
    await page.locator('.nav-item').getByText('Venue Catalogue', { exact: true }).click()
    await page.getByText(hall.name, { exact: true }).click()
    await expect(page.getByTestId('venue-clashes-none')).toBeVisible()
    await expect(page.getByTestId(`venue-clash-link-${hall.venueId}`)).toHaveCount(0)

    await page.getByRole('button', { name: 'Edit' }).click()
    await page.locator('#vf-setup').fill('30')
    await page.locator('#vf-turnaround').fill('45')
    await page.getByRole('button', { name: 'Save changes' }).click()

    const listed = page.getByTestId('venue-clash')
    await expect(listed).toHaveCount(3)
    await expect(listed.first()).toContainText(`"${booked.A.event.eventName}"`)
    await expect(listed.first()).toContainText(`"${booked.B.event.eventName}"`)
    await expect(listed.first().getByTestId('venue-clash-overlap')).toContainText(/11:30 to 12:45 UTC/)
    await expect(page.getByTestId('venue-clashes')).toContainText('Both bookings and their events are kept exactly as they are.')
    await expect(page.getByTestId(`venue-clash-link-${hall.venueId}`)).toHaveText(`${hall.name}: 3 clashes`)
  })
})
