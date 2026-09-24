import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venueBookingPayload } from './support/api-data.js'
import { createPendingBooking, notificationRequest, venueRequest } from './support/venue.js'

test.describe('SPM-63 Submit a venue booking request', () => {
  test('TC-SPM63-AC01 the assigned coordinator can request a venue for a planning event', async () => {
    const created = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      ...venueBookingPayload(260, 'e3', 'v2'),
    })
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    expect(created.body.status).toBe('pending')
    expect(created.body.eventId).toBe('e3')
  })

  test('TC-SPM63-AC02 the request carries event facts taken from the event record', async () => {
    const created = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      ...venueBookingPayload(261, 'e3', 'v3'),
    })
    expect(created.status).toBe(201)
    const viewed = await venueRequest('GET', `/venues/bookings/${created.body.bookingId}`, 'EC-01')
    expect(viewed.status).toBe(200)
    const text = JSON.stringify(viewed.body)
    expect(text).toMatch(/Partner Networking Night|e3/)
    expect(viewed.body.startsAt).toBeTruthy()
    expect(viewed.body.endsAt).toBeTruthy()
    expect(viewed.body.requirementsSnapshot).toBeTruthy()
  })

  test('TC-SPM63-AC03 a failed suitability check blocks submission', async () => {
    const created = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      ...venueBookingPayload(262, 'e3', 'v4'),
      requirementsSnapshot: 'Exhibition layout, 500 guests, loading dock',
    })
    expect([400, 409, 422]).toContain(created.status)
    expect(JSON.stringify(created.body)).toMatch(/not suitable|fail/i)
  })

  test('TC-SPM63-AC04 warnings can be submitted after acknowledgement and are carried to venue staff', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.goto('/app/events/e3/venues')
    await page.getByTestId('venue-select-v1').click()
    await expect(page.getByTestId('suitability-verdict')).toContainText(/warning/i)
    await page.getByTestId('suitability-acknowledge').check()
    await page.getByTestId('venue-request-submit').click()
    await expect(page.getByText(/request submitted|pending/i)).toBeVisible()

    await page.getByRole('button', { name: 'Log out' }).click()
    await login(page, account('VS-01'))
    await page.locator('.nav-item').getByText('Booking Requests', { exact: true }).click()
    await expect(page.getByTestId('booking-warnings').first()).toBeVisible()
  })

  test('TC-SPM63-AC05 submitting notifies venue staff and places the request in the pending queue', async () => {
    const created = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      ...venueBookingPayload(263, 'e3', 'v2'),
    })
    expect(created.status).toBe(201)
    const queue = await venueRequest('GET', '/venues/bookings?status=pending', 'VS-01')
    expect(queue.status).toBe(200)
    expect((queue.body || []).map((row) => row.bookingId)).toContain(created.body.bookingId)

    const notes = await notificationRequest('/notifications?userId=u3', 'VS-01')
    expect(notes.status).toBe(200)
    expect(JSON.stringify(notes.body)).toMatch(/booking|pending|e3|v2/i)
  })

  test('TC-SPM63-AC06 a pending request appears on the calendar and does not make the venue unavailable', async () => {
    const created = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      ...venueBookingPayload(264, 'e3', 'v3'),
    })
    expect(created.status).toBe(201)
    const calendar = await venueRequest('GET', '/venues/v3/calendar', 'VS-01')
    expect(calendar.status).toBe(200)
    const entry = (calendar.body || []).find((row) => row.bookingId === created.body.bookingId)
    expect(entry).toBeTruthy()
    expect(entry.kind || entry.status).toMatch(/pending/i)

    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(created.body.startsAt)}&endsAt=${encodeURIComponent(created.body.endsAt)}`,
      'EC-01',
    )
    expect((search.body || []).map((row) => row.venueId)).toContain('v3')
  })

  test('TC-SPM63-AC07 an event can have only one pending venue request at a time', async () => {
    const first = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      ...venueBookingPayload(265, 'e6', 'v2'),
    })
    expect(first.status).toBe(201)
    const second = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      ...venueBookingPayload(266, 'e6', 'v3'),
    })
    expect(second.status).toBe(409)
    expect(JSON.stringify(second.body)).toMatch(/pending|withdraw/i)
  })

  test('TC-SPM63-AC08 the coordinator can withdraw their pending request', async () => {
    const created = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      ...venueBookingPayload(267, 'e3', 'v2'),
    })
    expect(created.status).toBe(201)
    const withdrawn = await venueRequest(
      'POST',
      `/venues/bookings/${created.body.bookingId}/withdraw`,
      'EC-01',
    )
    expect(withdrawn.status).toBe(200)
    expect(withdrawn.body.status).toMatch(/withdrawn/i)
    const calendar = await venueRequest('GET', '/venues/v2/calendar', 'VS-01')
    const entry = (calendar.body || []).find((row) => row.bookingId === created.body.bookingId)
    expect(entry).toBeFalsy()
  })

  test('TC-SPM63-AC09 readiness shows the venue arrangement as in progress while a request is pending', async ({
    page,
  }) => {
    await createPendingBooking('EC-01', 268, { eventId: 'e3', venueId: 'v2' })
    await login(page, account('EC-01'))
    await page.goto('/app/events/e3')
    await expect(page.getByTestId('readiness-venue')).toBeVisible()
    await expect(page.getByTestId('readiness-venue')).toContainText(/in progress|pending/i)
  })
})
