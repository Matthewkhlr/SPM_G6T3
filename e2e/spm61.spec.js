import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, freshPeriod, requestVenue } from './support/venue-request.js'

// Seeded venues: v1 Marina Hall A (HarbourFront Centre, open every day 08:00-22:00
// UTC, Theatre 300, 30 min setup, 60 min turnaround), v2 Riverside Room 204
// (Boardroom 20, Classroom 80), v3 Exhibition Hall B (Suntec, Theatre 350, loading
// dock), v4 Skyline Boardroom (One Raffles Place, weekdays 08:00-18:00, Boardroom 20).
// Other specs add venues of their own, so results are checked for these four only.

function query(params) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    for (const item of [].concat(value)) search.append(key, item)
  }
  return `?${search}`
}

async function search(params = {}) {
  const response = await venueRequest('GET', `/venues/search${query(params)}`, 'EC-01')
  expect(response.status, JSON.stringify(response.body)).toBe(200)
  return response.body
}

const ids = (rows) => rows.map((row) => row.venueId)

// A confirmed booking: requested by the assigned coordinator, approved by Venue Staff.
async function confirmedBooking(venueId, period) {
  const event = await approvedEvent(THEATRE_EVENT)
  const sent = await requestVenue(event, venueId, period)
  expect(sent.status, JSON.stringify(sent.body)).toBe(201)
  const approved = await venueRequest('POST', `/venues/bookings/${sent.body.bookingId}/approve`, 'VS-01', {
    reason: 'SPM-61 search test',
  })
  expect(approved.status, JSON.stringify(approved.body)).toBe(200)
  return approved.body
}

function freshEvent() {
  const period = freshPeriod()
  return approvedEvent({ ...THEATRE_EVENT, proposedStartAt: period.startsAt, proposedEndAt: period.endsAt })
}

function shift(iso, minutes) {
  return new Date(new Date(iso).getTime() + minutes * 60 * 1000).toISOString()
}

test.describe('SPM-61 Search and filter venues against event requirements', () => {
  test('TC-SPM61-AC01 search from an event is pre-filled from the event and can be adjusted', async ({ page }) => {
    const event = await freshEvent()
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}/venues`)

    await expect(page.getByTestId('venue-search')).toBeVisible()
    await expect(page.getByTestId('venue-search-attendance')).toHaveValue('50')
    await expect(page.getByTestId('venue-search-layout')).toHaveValue('Theatre')
    await expect(page.getByTestId('venue-search-starts')).toHaveValue(event.proposedStartAt.slice(0, 16))
    await expect(page.getByTestId('venue-search-ends')).toHaveValue(event.proposedEndAt.slice(0, 16))
    await expect(page.getByTestId('venue-search-facility-Stage')).toBeChecked()

    await page.getByTestId('venue-search-attendance').fill('320')
    await page.getByTestId('venue-search-submit').click()

    await expect(page.getByTestId('venue-search-summary')).toBeVisible()
    await expect(page.getByTestId('venue-select-v1')).toHaveCount(0)
    await page.getByTestId('venue-search-reset').click()
    await expect(page.getByTestId('venue-select-v1')).toBeVisible()
  })

  test('TC-SPM61-AC02 filters cover time, capacity, location, layout, accessibility, and facilities', async () => {
    const period = freshPeriod()
    const rows = await search({
      startsAt: period.startsAt,
      endsAt: period.endsAt,
      minCapacity: 100,
      location: 'HarbourFront',
      layout: 'Theatre',
      accessibility: 'Wheelchair accessible',
      facility: ['PA system', 'Stage'],
    })
    expect(ids(rows)).toContain('v1')
    expect(ids(rows)).not.toContain('v3')
    expect(ids(await search({ location: 'Raffles' }))).toEqual(expect.arrayContaining(['v4']))
    expect(ids(await search({ location: 'Raffles' }))).not.toContain('v1')
  })

  test('TC-SPM61-AC03 a confirmed booking excludes the venue, including its setup and turnaround', async () => {
    const period = freshPeriod()
    await confirmedBooking('v1', period)

    expect(ids(await search({ startsAt: period.startsAt, endsAt: period.endsAt }))).not.toContain('v1')
    // Starts 30 minutes after the booking ends: the event times do not overlap, but this
    // search's 30 minute setup runs into the booking's 60 minute turnaround.
    const soonAfter = await search({ startsAt: shift(period.endsAt, 30), endsAt: shift(period.endsAt, 150) })
    expect(ids(soonAfter)).not.toContain('v1')
    // Starting 90 minutes after leaves exactly turnaround plus setup, so the windows only touch.
    const touching = await search({ startsAt: shift(period.endsAt, 90), endsAt: shift(period.endsAt, 210) })
    expect(ids(touching)).toContain('v1')
  })

  test('TC-SPM61-AC03 an unavailability period or active tentative hold excludes the venue', async () => {
    test.skip(
      true,
      'Recording unavailability is SPM-9 and tentative holds are SPM-116, neither built yet. The unavailability rule is unit-tested in test_venue_search.py.',
    )
  })

  test('TC-SPM61-AC04 an expired tentative hold does not exclude the venue', async () => {
    test.skip(true, 'Tentative holds are SPM-116, not built yet; remove this skip when it ships.')
  })

  test('TC-SPM61-AC05 an unsupported layout or too little capacity in that layout excludes the venue', async () => {
    const boardroom = await search({ layout: 'Boardroom', minCapacity: 20 })
    expect(ids(boardroom)).toEqual(expect.arrayContaining(['v2', 'v4']))
    expect(ids(boardroom)).not.toContain('v1')
    const tooMany = await search({ layout: 'Boardroom', minCapacity: 21 })
    expect(ids(tooMany)).not.toContain('v2')
    expect(ids(tooMany)).not.toContain('v4')
  })

  test('TC-SPM61-AC06 a missing facility or accessibility feature excludes the venue', async () => {
    const dock = await search({ facility: 'Loading dock' })
    expect(ids(dock)).toContain('v3')
    expect(ids(dock)).not.toContain('v1')
    const restrooms = await search({ accessibility: 'Accessible restrooms nearby' })
    expect(ids(restrooms)).toEqual(expect.arrayContaining(['v1', 'v3']))
    expect(ids(restrooms)).not.toContain('v4')
  })

  test('TC-SPM61-AC07 a time outside the opening hours excludes the venue', async () => {
    const period = freshPeriod()
    const evening = await search({ startsAt: shift(period.startsAt, 540), endsAt: shift(period.startsAt, 600) })
    expect(ids(evening)).toContain('v1')
    expect(ids(evening)).not.toContain('v4')
  })

  test('TC-SPM61-AC08 each result shows its capacity in the layout and the headroom', async ({ page }) => {
    const [row] = (await search({ layout: 'Theatre', minCapacity: 250 })).filter((item) => item.venueId === 'v1')
    expect(row).toMatchObject({ layout: 'Theatre', layoutCapacity: 300, headroom: 50 })

    const event = await freshEvent()
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}/venues`)
    await page.getByTestId('venue-search-submit').click()
    await expect(page.getByTestId('venue-select-v1')).toContainText('Capacity 300 in Theatre · 250 spare')
  })

  test('TC-SPM61-AC09 a venue with an overlapping pending request is still shown, marked contested', async ({
    page,
  }) => {
    const event = await freshEvent()
    const sent = await requestVenue(
      event,
      'v3',
      {
        startsAt: event.proposedStartAt,
        endsAt: event.proposedEndAt,
        setupStartsAt: event.proposedStartAt,
        teardownEndsAt: event.proposedEndAt,
      },
      { acknowledgeWarnings: true },
    )
    expect(sent.status, JSON.stringify(sent.body)).toBe(201)

    const rows = await search({ startsAt: event.proposedStartAt, endsAt: event.proposedEndAt })
    expect(rows.find((row) => row.venueId === 'v3')).toMatchObject({ contested: true })
    // The searching event's own request does not make the venue contested for it.
    const own = await search({ startsAt: event.proposedStartAt, endsAt: event.proposedEndAt, eventId: event.eventId })
    expect(own.find((row) => row.venueId === 'v3')).toMatchObject({ contested: false })

    const other = await approvedEvent({
      ...THEATRE_EVENT,
      proposedStartAt: event.proposedStartAt,
      proposedEndAt: event.proposedEndAt,
    })
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${other.eventId}/venues`)
    // Exhibition Hall B has no stage, which this event asks for, so drop that filter first.
    await page.getByTestId('venue-search-facility-Stage').uncheck()
    await page.getByTestId('venue-search-submit').click()
    await expect(page.getByTestId('venue-contested-v3')).toBeVisible()
  })
})
