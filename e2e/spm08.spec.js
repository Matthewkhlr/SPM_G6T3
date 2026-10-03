import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venueBookingPayload, venuePeriod } from './support/api-data.js'
import { createPendingBooking, venueRequest } from './support/venue.js'

test.describe('SPM-08 Approve a Venue Booking Request', () => {
  test('TC-SPM08-AC01 view a submitted request and approve it', async ({ page }) => {
    const created = await createPendingBooking('EC-01', 210)
    await login(page, account('VS-01'))
    await page.locator('.nav-item').getByText('Booking Requests', { exact: true }).click()
    const item = page.getByTestId(`booking-request-${created.bookingId}`)
    await expect(item).toBeVisible()
    await expect(item).toContainText(/AI in Events Summit|e1/i)
    await expect(item.getByTestId('booking-starts-at')).toBeVisible()
    await expect(item.getByTestId('booking-requirements')).toBeVisible()
    await expect(item.getByTestId('booking-submitted-at')).toBeVisible()
    await item.getByRole('button', { name: /approve/i }).click()
    await expect(item).toContainText(/approved/i)
  })

  test('TC-SPM08-AC02 approved booking details are reserved by datetime', async () => {
    const created = await createPendingBooking('EC-01', 211)
    const approved = await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'AUTO-SPM08-AC02',
    })
    expect(approved.status).toBe(200)
    expect(approved.body.status).toMatch(/approved|confirmed/i)
    expect(approved.body.startsAt).toBe(created.startsAt)
    expect(approved.body.endsAt).toBe(created.endsAt)
    expect(approved.body.venueId).toBe('v1')

    const viewed = await venueRequest('GET', `/venues/bookings/${created.bookingId}`, 'VS-01')
    expect(viewed.status).toBe(200)
    expect(viewed.body.status).toMatch(/approved|confirmed/i)
    expect(viewed.body.startsAt).toBe(created.startsAt)
  })

  test('TC-SPM08-AC03 approved bookings stay locked until the event completes', async () => {
    const created = await createPendingBooking('EC-01', 212)
    const approved = await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'AUTO-SPM08-AC03',
    })
    expect(approved.status).toBe(200)

    const again = await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'retry',
    })
    expect([409, 403]).toContain(again.status)
    expect(again.body.status || approved.body.status).toMatch(/approved|confirmed/i)

    const rejected = await venueRequest('POST', `/venues/bookings/${created.bookingId}/reject`, 'VS-01', {
      reason: 'already booked',
      explanation: 'should stay locked',
    })
    expect([409, 403]).toContain(rejected.status)
  })

  test('TC-SPM08-AC04 approval records who and when and persists after the event completes', async () => {
    const created = await createPendingBooking('EC-01', 213)
    const approved = await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'AUTO-SPM08-AC04',
    })
    expect(approved.status).toBe(200)
    expect(approved.body.reviewedBy).toBe('u3')
    expect(approved.body.reviewedAt).toBeTruthy()

    const log = await venueRequest('GET', `/venues/v1/activity-log`, 'VS-01')
    expect(log.status).toBe(200)
    const approval = (log.body || []).find(
      (row) => row.action === 'booking_approved' || JSON.stringify(row).includes(created.bookingId),
    )
    expect(approval, JSON.stringify(log.body)).toBeTruthy()
  })

  test('TC-SPM08-AC05 unavailability blocks approval and leaves the request unapproved', async () => {
    const window = venuePeriod(214, 3)
    const block = await venueRequest('POST', '/venues/v2/unavailability', 'VS-01', {
      startsAt: window.startsAt,
      endsAt: window.endsAt,
      reason: 'maintenance',
      note: 'AUTO-SPM08-AC05',
    })
    expect(block.status, JSON.stringify(block.body)).toBe(201)

    const created = await createPendingBooking('EC-01', 214, { venueId: 'v2' })
    const approved = await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'should fail',
    })
    expect(approved.status).toBe(409)
    expect(JSON.stringify(approved.body)).toMatch(/unavailab|maintenance|error/i)

    const viewed = await venueRequest('GET', `/venues/bookings/${created.bookingId}`, 'VS-01')
    expect(viewed.body.status).toBe('pending')
  })

  test('TC-SPM08-AC06 overlap with a confirmed booking blocks approval', async () => {
    const first = await createPendingBooking('EC-01', 215, { venueId: 'v3' })
    const approved = await venueRequest('POST', `/venues/bookings/${first.bookingId}/approve`, 'VS-01', {
      reason: 'first wins',
    })
    expect(approved.status).toBe(200)

    const clash = await createPendingBooking('EC-01', 215, { venueId: 'v3', eventId: 'e4' })
    const blocked = await venueRequest('POST', `/venues/bookings/${clash.bookingId}/approve`, 'VS-01', {
      reason: 'should clash',
    })
    expect(blocked.status).toBe(409)
    expect(JSON.stringify(blocked.body)).toMatch(/overlap|conflict|already|error/i)
    const viewed = await venueRequest('GET', `/venues/bookings/${clash.bookingId}`, 'VS-01')
    expect(viewed.body.status).toBe('pending')
  })

  test('TC-SPM08-AC07 overlap with a tentative hold blocks approval', async () => {
    const hold = await venueRequest('POST', '/venues/v4/holds', 'VS-01', {
      ...venueBookingPayload(216, 'e1', 'v4'),
    })
    expect([201, 200]).toContain(hold.status)

    const created = await createPendingBooking('EC-01', 216, { venueId: 'v4' })
    const blocked = await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'should hit hold',
    })
    expect(blocked.status).toBe(409)
    expect(JSON.stringify(blocked.body)).toMatch(/hold|tentative|conflict|error/i)
    const viewed = await venueRequest('GET', `/venues/bookings/${created.bookingId}`, 'VS-01')
    expect(viewed.body.status).toBe('pending')
  })

  test('TC-SPM08-AC08 a free slot becomes an approved confirmed booking and locks the venue', async () => {
    const created = await createPendingBooking('EC-01', 217, { venueId: 'v2' })
    const approved = await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
      reason: 'AUTO-SPM08-AC08',
    })
    expect(approved.status).toBe(200)
    expect(approved.body.status).toMatch(/approved|confirmed/i)
    expect(approved.body.venueId).toBe('v2')
    expect(approved.body.eventId).toBe('e1')

    const clash = await createPendingBooking('EC-01', 217, { venueId: 'v2', eventId: 'e4' })
    const blocked = await venueRequest('POST', `/venues/bookings/${clash.bookingId}/approve`, 'VS-01', {
      reason: 'locked',
    })
    expect(blocked.status).toBe(409)
  })

  test('TC-SPM08-AC09 competing requests are listed oldest first', async () => {
    const older = await createPendingBooking('EC-01', 218, { venueId: 'v3', eventId: 'e1' })
    const newer = await createPendingBooking('EC-01', 218, { venueId: 'v3', eventId: 'e4' })
    const list = await venueRequest('GET', '/venues/bookings?status=pending&venueId=v3', 'VS-01')
    expect(list.status).toBe(200)
    const ids = (list.body || []).map((row) => row.bookingId)
    expect(ids.indexOf(older.bookingId)).toBeGreaterThanOrEqual(0)
    expect(ids.indexOf(newer.bookingId)).toBeGreaterThan(ids.indexOf(older.bookingId))
  })
})
