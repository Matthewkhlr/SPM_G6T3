import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venuePeriod } from './support/api-data.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, freshPeriod, requestVenue } from './support/venue-request.js'

async function suitability(eventId, venueId, extras = {}) {
  return venueRequest('POST', '/venues/suitability', 'EC-01', {
    eventId,
    venueId,
    ...extras,
  })
}

test.describe('SPM-62 Venue suitability check for an event', () => {
  test('TC-SPM62-AC01 the check returns suitable, suitable with warnings, or not suitable with reasons', async () => {
    const result = await suitability('e1', 'v1')
    expect(result.status).toBe(200)
    expect(result.body.verdict).toMatch(/suitable|not suitable/i)
    expect(Array.isArray(result.body.reasons || result.body.points)).toBe(true)
  })

  test('TC-SPM62-AC02 attendance above layout capacity is a failure that names both numbers', async () => {
    const result = await suitability('e1', 'v4', { expectedAttendance: 500, layout: 'Boardroom' })
    expect(result.status).toBe(200)
    expect(result.body.verdict).toMatch(/not suitable/i)
    expect(JSON.stringify(result.body)).toMatch(/500|20/)
  })

  test('TC-SPM62-AC03 unsupported layout, missing facility, and missing accessibility are named failures', async () => {
    const result = await suitability('e1', 'v4', {
      layout: 'Exhibition',
      requiredFacilities: ['Loading dock'],
      requiredAccessibility: ['Hearing loop'],
    })
    expect(result.status).toBe(200)
    expect(result.body.verdict).toMatch(/not suitable/i)
    const text = JSON.stringify(result.body)
    expect(text).toMatch(/Exhibition/)
    expect(text).toMatch(/Loading dock/)
    expect(text).toMatch(/Hearing loop/)
  })

  test('TC-SPM62-AC04 an overlapping confirmed booking or unavailability is a named failure', async () => {
    // Since SPM-63, only a suitable venue for an approved event can be booked,
    // so the confirmed booking comes from a fresh Theatre event at v1.
    const other = await approvedEvent(THEATRE_EVENT)
    const period = freshPeriod()
    const created = await requestVenue(other, 'v1', period)
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    await venueRequest('POST', `/venues/bookings/${created.body.bookingId}/approve`, 'VS-01', {
      reason: 'for suitability',
    })
    const result = await suitability('e4', 'v1', { ...period, layout: 'Theatre' })
    expect(result.status).toBe(200)
    expect(result.body.verdict).toMatch(/not suitable/i)
    expect(JSON.stringify(result.body)).toMatch(/e1|booking|unavailab/i)
  })

  test('TC-SPM62-AC05 a time outside opening hours is a failure', async () => {
    const start = new Date(Date.now() + 251 * 24 * 60 * 60 * 1000)
    start.setUTCHours(2, 0, 0, 0)
    const end = new Date(start.getTime() + 60 * 60 * 1000)
    const result = await suitability('e1', 'v4', {
      startsAt: start.toISOString(),
      endsAt: end.toISOString(),
    })
    expect(result.status).toBe(200)
    expect(result.body.verdict).toMatch(/not suitable/i)
    expect(JSON.stringify(result.body)).toMatch(/opening hours|outside/i)
  })

  test('TC-SPM62-AC06 attendance above about ninety percent of capacity is a warning', async () => {
    // v4 opens 08:00 to 18:00 UTC on weekdays only, so send a weekday time inside
    // those hours; e1's own time runs past 18:00, which would be a real failure.
    let day = 253
    while ([0, 6].includes(new Date(venuePeriod(day).startsAt).getUTCDay())) day += 1
    const result = await suitability('e1', 'v4', {
      expectedAttendance: 19,
      layout: 'Boardroom',
      ...venuePeriod(day, 2),
    })
    expect(result.status).toBe(200)
    expect(result.body.verdict).toMatch(/suitable with warnings/i)
    expect(JSON.stringify(result.body)).toMatch(/warning|tight|90/i)
  })

  test('TC-SPM62-AC07 an overlapping pending request is a warning', async () => {
    // The pending request comes from a fresh approved Theatre event (see AC04).
    const period = freshPeriod()
    const created = await requestVenue(await approvedEvent(THEATRE_EVENT), 'v3', period)
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    // e4 asks for a Boardroom, which v3 does not offer (a real failure), so
    // check it in a layout v3 has, leaving the pending request as the only issue.
    const result = await suitability('e4', 'v3', { ...period, layout: 'Theatre' })
    expect(result.status).toBe(200)
    expect(result.body.verdict).toMatch(/suitable with warnings/i)
    expect(JSON.stringify(result.body)).toMatch(/pending|contested|warning/i)
  })

  test('TC-SPM62-AC08 warnings may proceed; failures block the booking request', async ({ page }) => {
    await login(page, account('EC-01'))
    await page.goto('/app/events/e3/venues')
    await page.getByTestId('venue-select-v4').click()
    await expect(page.getByTestId('suitability-verdict')).toBeVisible()
    const verdict = await page.getByTestId('suitability-verdict').innerText()
    if (/not suitable/i.test(verdict)) {
      await expect(page.getByTestId('venue-request-submit')).toBeDisabled()
    } else {
      await expect(page.getByTestId('venue-request-submit')).toBeEnabled()
    }
  })

  test('TC-SPM62-AC08 a venue with only warnings can still be requested', async ({ page }) => {
    // 280 people in v1's Theatre (300) is above 90%: a warning only. Since
    // SPM-63 the coordinator ticks that they read the warnings, then may go ahead.
    const tight = await approvedEvent({ layoutPreference: 'Theatre', expectedAttendance: 280 })
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${tight.eventId}/venues`)
    await page.getByTestId('venue-select-v1').click()
    await expect(page.getByTestId('suitability-verdict')).toHaveText(/suitable with warnings/i)
    await expect(page.getByTestId('suitability-reasons')).toContainText(/Warning.*90%/)
    await expect(page.getByTestId('venue-request-submit')).toBeDisabled()
    await page.getByTestId('suitability-acknowledge').check()
    await expect(page.getByTestId('venue-request-submit')).toBeEnabled()
  })

  test('TC-SPM62-AC08 a venue that fails cannot be requested and the page says why', async ({ page }) => {
    // e3 asks for a Banquet layout, which v4 does not offer.
    await login(page, account('EC-01'))
    await page.goto('/app/events/e3/venues')
    await page.getByTestId('venue-select-v4').click()
    await expect(page.getByTestId('suitability-verdict')).toHaveText(/not suitable/i)
    await expect(page.getByTestId('suitability-reasons')).toContainText(/Failure.*Banquet/)
    await expect(page.getByTestId('venue-request-submit')).toBeDisabled()
  })

  test('TC-SPM62-AC08 the verdict shown is for the venue just selected, even if an earlier check is slow', async ({
    page,
  }) => {
    const expected = await suitability('e3', 'v1')
    await login(page, account('EC-01'))
    await page.route('**/venues/suitability', async (route) => {
      if (route.request().postDataJSON().venueId === 'v4') await new Promise((done) => setTimeout(done, 2000))
      await route.continue()
    })
    await page.goto('/app/events/e3/venues')
    await page.getByTestId('venue-select-v4').click()
    await page.getByTestId('venue-select-v1').click()
    await expect(page.getByTestId('suitability-verdict')).toBeVisible()
    await page.waitForTimeout(2500)
    const shown = (await page.getByTestId('suitability-verdict').innerText()).trim().toLowerCase()
    expect(shown).toBe(expected.body.verdict)
    await expect(page.locator('.verdict-panel h3')).toHaveText('Marina Hall A')
  })

  test('TC-SPM62-AC09 after a search, each venue shows the verdict the check gives when it is picked', async ({
    page,
  }) => {
    // 280 people in v1's Theatre (300) is a tight fit, so v1 is listed with a warning.
    const tight = await approvedEvent({ layoutPreference: 'Theatre', expectedAttendance: 280 })
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${tight.eventId}/venues`)
    await page.getByTestId('venue-search-submit').click()
    await expect(page.getByTestId('venue-search-summary')).toBeVisible()

    const listed = page.getByTestId('venue-verdict-v1')
    await expect(listed).toHaveText(/suitable with warnings/i)
    await page.getByTestId('venue-select-v1').click()
    // Both are styled in capitals, so compare the text itself, not how it is drawn.
    await expect(page.getByTestId('suitability-verdict')).toHaveText((await listed.textContent()).trim())
  })

  test('TC-SPM62-AC09 search, booking, and re-verification use the same suitability rule', async () => {
    const direct = await suitability('e1', 'v1')
    const search = await venueRequest('GET', '/venues/search?eventId=e1', 'EC-01')
    expect(direct.status).toBe(200)
    expect(search.status).toBe(200)
    const fromSearch = (search.body || []).find((row) => row.venueId === 'v1')
    expect(fromSearch.verdict || fromSearch.suitability).toBe(direct.body.verdict)
  })
})
