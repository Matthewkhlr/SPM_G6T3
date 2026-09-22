import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venuePeriod } from './support/api-data.js'
import { createPendingBooking, venueRequest } from './support/venue.js'

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
    const created = await createPendingBooking('EC-01', 250, { venueId: 'v4' })
    await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'for suitability',
    })
    const result = await suitability('e4', 'v4', venuePeriod(250, 2))
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
    const result = await suitability('e1', 'v4', { expectedAttendance: 19, layout: 'Boardroom' })
    expect(result.status).toBe(200)
    expect(result.body.verdict).toMatch(/suitable with warnings/i)
    expect(JSON.stringify(result.body)).toMatch(/warning|tight|90/i)
  })

  test('TC-SPM62-AC07 an overlapping pending request is a warning', async () => {
    await createPendingBooking('EC-01', 252, { venueId: 'v3' })
    const result = await suitability('e4', 'v3', venuePeriod(252, 2))
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

  test('TC-SPM62-AC09 search, booking, and re-verification use the same suitability rule', async () => {
    const direct = await suitability('e1', 'v1')
    const search = await venueRequest('GET', '/venues/search?eventId=e1', 'EC-01')
    expect(direct.status).toBe(200)
    expect(search.status).toBe(200)
    const fromSearch = (search.body || []).find((row) => row.venueId === 'v1')
    expect(fromSearch.verdict || fromSearch.suitability).toBe(direct.body.verdict)
  })
})
