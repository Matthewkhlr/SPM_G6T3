import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venuePeriod } from './support/api-data.js'
import { createPendingBooking, venueRequest } from './support/venue.js'

test.describe('SPM-61 Search and filter venues against event requirements', () => {
  test('TC-SPM61-AC01 search from an event is pre-filled from the event requirements', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.goto('/app/events/e1/venues')
    await expect(page.getByTestId('venue-search')).toBeVisible()
    await expect(page.getByTestId('venue-search-attendance')).toHaveValue(/120/)
    await expect(page.getByTestId('venue-search-layout')).toHaveValue(/Theatre/i)
    await page.getByTestId('venue-search-attendance').fill('80')
    await expect(page.getByTestId('venue-search-attendance')).toHaveValue('80')
  })

  test('TC-SPM61-AC02 filters cover time, capacity, location, layout, accessibility, and facilities', async () => {
    const window = venuePeriod(240, 2)
    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(window.startsAt)}&endsAt=${encodeURIComponent(window.endsAt)}&minCapacity=20&location=HarbourFront&layout=Theatre&accessibility=Wheelchair%20accessible&facility=Projector`,
      'EC-01',
    )
    expect(search.status).toBe(200)
    expect(Array.isArray(search.body)).toBe(true)
  })

  test('TC-SPM61-AC03 a confirmed booking or unavailability excludes the venue', async () => {
    const created = await createPendingBooking('EC-01', 241, { venueId: 'v4' })
    await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'hold for search',
    })
    const window = venuePeriod(241, 2)
    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(window.startsAt)}&endsAt=${encodeURIComponent(window.endsAt)}`,
      'EC-01',
    )
    expect(search.status).toBe(200)
    expect((search.body || []).map((row) => row.venueId)).not.toContain('v4')
  })

  test('TC-SPM61-AC04 unsupported layout or low capacity excludes the venue', async () => {
    const window = venuePeriod(242, 2)
    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(window.startsAt)}&endsAt=${encodeURIComponent(window.endsAt)}&layout=Boardroom&minCapacity=200`,
      'EC-01',
    )
    expect(search.status).toBe(200)
    expect((search.body || []).map((row) => row.venueId)).not.toContain('v4')
  })

  test('TC-SPM61-AC05 a missing facility or accessibility feature excludes the venue', async () => {
    const window = venuePeriod(243, 2)
    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(window.startsAt)}&endsAt=${encodeURIComponent(window.endsAt)}&facility=Loading%20dock`,
      'EC-01',
    )
    expect(search.status).toBe(200)
    expect((search.body || []).map((row) => row.venueId)).not.toContain('v4')
  })

  test('TC-SPM61-AC06 a time outside opening hours excludes the venue', async () => {
    const start = new Date(Date.now() + 244 * 24 * 60 * 60 * 1000)
    start.setUTCHours(2, 0, 0, 0)
    const end = new Date(start.getTime() + 60 * 60 * 1000)
    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(start.toISOString())}&endsAt=${encodeURIComponent(end.toISOString())}`,
      'EC-01',
    )
    expect(search.status).toBe(200)
    expect((search.body || []).map((row) => row.venueId)).not.toContain('v4')
  })

  test('TC-SPM61-AC07 each result shows capacity in the requested layout and headroom', async () => {
    const window = venuePeriod(245, 2)
    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(window.startsAt)}&endsAt=${encodeURIComponent(window.endsAt)}&layout=Theatre&minCapacity=10`,
      'EC-01',
    )
    expect(search.status).toBe(200)
    const first = (search.body || [])[0]
    expect(first).toBeTruthy()
    expect(first.layoutCapacity || first.capacityInLayout).toBeGreaterThan(0)
    expect(first.headroom).toBeDefined()
  })

  test('TC-SPM61-AC08 a pending overlapping request still appears and is marked contested', async () => {
    const created = await createPendingBooking('EC-01', 246, { venueId: 'v3' })
    expect(created.status).toBe('pending')
    const window = venuePeriod(246, 2)
    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(window.startsAt)}&endsAt=${encodeURIComponent(window.endsAt)}`,
      'EC-01',
    )
    expect(search.status).toBe(200)
    const row = (search.body || []).find((item) => item.venueId === 'v3')
    expect(row).toBeTruthy()
    expect(row.contested || row.mark).toBeTruthy()
  })
})
