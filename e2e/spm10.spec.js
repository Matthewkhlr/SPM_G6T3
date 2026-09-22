import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { createPendingBooking, venueRequest } from './support/venue.js'

test.describe('SPM-10 Reject a Venue Booking Request', () => {
  test('TC-SPM10-AC01 view the full details of a pending request', async ({ page }) => {
    const created = await createPendingBooking('EC-01', 230)
    await login(page, account('VS-01'))
    await page.locator('.nav-item').getByText('Booking Requests', { exact: true }).click()
    const item = page.getByTestId(`booking-request-${created.bookingId}`)
    await expect(item).toBeVisible()
    await item.click()
    await expect(page.getByTestId('booking-detail')).toBeVisible()
    await expect(page.getByTestId('booking-detail')).toContainText(created.bookingId)
    await expect(page.getByTestId('booking-detail-starts')).toBeVisible()
    await expect(page.getByTestId('booking-detail-requirements')).toBeVisible()
  })

  test('TC-SPM10-AC02 reject requires a mandatory reason', async () => {
    const created = await createPendingBooking('EC-01', 231)
    const missing = await venueRequest('POST', `/venues/bookings/${created.bookingId}/reject`, 'VS-01', {})
    expect([400, 422]).toContain(missing.status)

    const rejected = await venueRequest('POST', `/venues/bookings/${created.bookingId}/reject`, 'VS-01', {
      reason: 'unsuitable for the requirements',
      explanation: 'Layout does not fit.',
    })
    expect(rejected.status).toBe(200)
    expect(rejected.body.status).toMatch(/rejected/i)
    expect(rejected.body.decisionReason).toMatch(/unsuitable|Layout/i)
  })

  test('TC-SPM10-AC03 an alternative venue may be suggested and is optional', async () => {
    const withAlt = await createPendingBooking('EC-01', 232)
    const suggested = await venueRequest('POST', `/venues/bookings/${withAlt.bookingId}/reject`, 'VS-01', {
      reason: 'already booked',
      explanation: 'Try Hall B',
      alternativeVenueIds: ['v2'],
    })
    expect(suggested.status).toBe(200)
    expect(suggested.body.alternativeVenueIds || suggested.body.suggestedVenues).toEqual(
      expect.arrayContaining(['v2']),
    )

    const withoutAlt = await createPendingBooking('EC-01', 233)
    const plain = await venueRequest('POST', `/venues/bookings/${withoutAlt.bookingId}/reject`, 'VS-01', {
      reason: 'venue unavailable',
      explanation: 'Closed that day',
    })
    expect(plain.status).toBe(200)
    expect(plain.body.status).toMatch(/rejected/i)
  })

  test('TC-SPM10-AC04 a rejected request leaves the queue and is read-only', async () => {
    const created = await createPendingBooking('EC-01', 234)
    const rejected = await venueRequest('POST', `/venues/bookings/${created.bookingId}/reject`, 'VS-01', {
      reason: 'other',
      explanation: 'No longer needed',
    })
    expect(rejected.status).toBe(200)
    expect(rejected.body.status).toMatch(/rejected/i)

    const queue = await venueRequest('GET', '/venues/bookings?status=pending', 'VS-01')
    expect(queue.status).toBe(200)
    const ids = (queue.body || []).map((row) => row.bookingId)
    expect(ids).not.toContain(created.bookingId)

    const approve = await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'too late',
    })
    expect([409, 403]).toContain(approve.status)
  })

  test('TC-SPM10-AC05 a rejected request holds nothing on the venue', async () => {
    const created = await createPendingBooking('EC-01', 235, { venueId: 'v2' })
    await venueRequest('POST', `/venues/bookings/${created.bookingId}/reject`, 'VS-01', {
      reason: 'already booked',
      explanation: 'Released',
    })
    const next = await createPendingBooking('EC-01', 235, { venueId: 'v2', eventId: 'e4' })
    const approved = await venueRequest('POST', `/venues/bookings/${next.bookingId}/approve`, 'VS-01', {
      reason: 'slot free',
    })
    expect(approved.status).toBe(200)
  })

  test('TC-SPM10-AC06 the rejecter, reason, and datetime are recorded', async () => {
    const created = await createPendingBooking('EC-01', 236)
    const rejected = await venueRequest('POST', `/venues/bookings/${created.bookingId}/reject`, 'VS-01', {
      reason: 'insufficient setup time',
      explanation: 'Turnaround too tight',
    })
    expect(rejected.status).toBe(200)
    expect(rejected.body.reviewedBy).toBe('u3')
    expect(rejected.body.reviewedAt).toBeTruthy()
    expect(rejected.body.decisionReason).toBeTruthy()
  })

  test('TC-SPM10-AC07 pending requests do not auto-expire', async () => {
    const created = await createPendingBooking('EC-01', 237)
    expect(created.status).toBe('pending')
    expect(created.expiresAt || created.deadlineAt).toBeFalsy()
    const viewed = await venueRequest('GET', `/venues/bookings/${created.bookingId}`, 'VS-01')
    expect(viewed.status).toBe(200)
    expect(viewed.body.status).toBe('pending')
    expect(viewed.body.expiresAt || viewed.body.deadlineAt).toBeFalsy()
  })
})
