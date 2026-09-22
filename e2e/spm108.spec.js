import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venuePeriod, venueUnavailabilityPayload } from './support/api-data.js'
import { createPendingBooking, venueRequest } from './support/venue.js'

test.describe('SPM-108 Venue availability calendar', () => {
  test('TC-SPM108-AC01 the calendar shows confirmed bookings, pending requests, and unavailability', async () => {
    const pending = await createPendingBooking('EC-01', 280, { venueId: 'v2' })
    const confirmed = await createPendingBooking('EC-01', 281, { venueId: 'v2', eventId: 'e4' })
    await venueRequest('POST', `/venues/bookings/${confirmed.bookingId}/approve`, 'VS-01', {
      reason: 'calendar confirmed',
    })
    const block = await venueRequest(
      'POST',
      '/venues/v2/unavailability',
      'VS-01',
      venueUnavailabilityPayload(282),
    )
    expect(block.status).toBe(201)

    const calendar = await venueRequest('GET', '/venues/v2/calendar', 'VS-01')
    expect(calendar.status).toBe(200)
    const payload = JSON.stringify(calendar.body)
    expect(payload).toContain(pending.bookingId)
    expect(payload).toContain(confirmed.bookingId)
    expect(payload).toContain(block.body.unavailabilityId)
  })

  test('TC-SPM108-AC02 each entry kind is visually distinct', async ({ page }) => {
    await login(page, account('VS-01'))
    await page.goto('/app/venues/v1/calendar')
    await expect(page.getByTestId('calendar-kind-confirmed').first()).toBeVisible()
    await expect(page.getByTestId('calendar-kind-pending').first()).toBeVisible()
    const confirmedClass = await page.getByTestId('calendar-kind-confirmed').first().getAttribute('data-kind')
    const pendingClass = await page.getByTestId('calendar-kind-pending').first().getAttribute('data-kind')
    expect(confirmedClass).not.toBe(pendingClass)
  })

  test('TC-SPM108-AC03 an entry shows event name, organisation, and time, and opens the record', async ({
    page,
  }) => {
    await login(page, account('VS-01'))
    await page.goto('/app/venues/v1/calendar')
    const entry = page.getByTestId('calendar-booking-vb-soon')
    await expect(entry).toBeVisible()
    await expect(entry).toContainText(/AI in Events Summit/)
    await expect(entry).toContainText(/Apex Partners/)
    await entry.click()
    await expect(page).toHaveURL(/e1|booking|vb-soon/i)
  })

  test('TC-SPM108-AC04 times outside opening hours are shown as unavailable', async ({ page }) => {
    await login(page, account('VS-01'))
    await page.goto('/app/venues/v4/calendar')
    await expect(page.getByTestId('calendar-outside-hours').first()).toBeVisible()
  })

  test('TC-SPM108-AC05 the calendar can be viewed by week and month, including past dates', async ({
    page,
  }) => {
    await login(page, account('VS-01'))
    await page.goto('/app/venues/v1/calendar')
    await page.getByTestId('calendar-view-week').click()
    await expect(page.getByTestId('venue-calendar')).toHaveAttribute('data-view', 'week')
    await page.getByTestId('calendar-view-month').click()
    await expect(page.getByTestId('venue-calendar')).toHaveAttribute('data-view', 'month')
    await page.getByTestId('calendar-prev').click()
    await expect(page.getByTestId('venue-calendar')).toBeVisible()
  })

  test('TC-SPM108-AC06 a new decision appears the next time the calendar is opened', async ({ page }) => {
    const created = await createPendingBooking('EC-01', 283, { venueId: 'v3' })
    await login(page, account('VS-01'))
    await page.goto('/app/venues/v3/calendar')
    await expect(page.getByTestId(`calendar-booking-${created.bookingId}`)).toBeVisible()
    await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'refresh',
    })
    await page.goto('/app/venues/v3/calendar')
    await expect(page.getByTestId(`calendar-booking-${created.bookingId}`)).toHaveAttribute(
      'data-kind',
      /confirmed|approved/,
    )
  })

  test('TC-SPM108-AC07 internal roles can read any venue calendar', async () => {
    for (const id of ['EC-01', 'VS-01', 'TS-01']) {
      const calendar = await venueRequest('GET', '/venues/v1/calendar', id)
      expect(calendar.status, id).toBe(200)
    }
    const denied = await venueRequest('GET', '/venues/v1/calendar', 'ATT-01')
    expect(denied.status).toBe(403)
  })

  test('TC-SPM108-AC08 a range with nothing booked shows an empty calendar, not an error', async ({
    page,
  }) => {
    const far = venuePeriod(400, 2)
    const calendar = await venueRequest(
      'GET',
      `/venues/v4/calendar?from=${encodeURIComponent(far.startsAt)}&to=${encodeURIComponent(far.endsAt)}`,
      'VS-01',
    )
    expect(calendar.status).toBe(200)
    expect(calendar.body.error).toBeFalsy()

    await login(page, account('VS-01'))
    await page.goto('/app/venues/v4/calendar?from=2099-01-01&to=2099-01-07')
    await expect(page.getByTestId('venue-calendar-empty')).toBeVisible()
  })
})
