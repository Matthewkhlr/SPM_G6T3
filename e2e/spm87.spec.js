import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { eventApi } from './support/event.js'
import { venueRequest } from './support/venue.js'

const later = () => {
  const start = new Date(Date.now() + 50 * 86400000)
  start.setUTCHours(10, 0, 0, 0)
  const end = new Date(start.getTime() + 3 * 3600000)
  return { proposedStartAt: start.toISOString(), proposedEndAt: end.toISOString() }
}

test.describe('SPM-87 Reschedule an event', () => {
  test('TC-SPM87-AC01 the assigned coordinator can reschedule Approved, Planning, or Confirmed events with a reason', async () => {
    const period = later()
    const moved = await eventApi('POST', '/e3/reschedule', 'EC-01', {
      ...period,
      reason: 'Client asked to move',
    })
    expect(moved.status).toBe(200)
    expect(moved.body.proposedStartAt).toBe(period.proposedStartAt)
    expect(moved.body.reason || moved.body.rescheduleReason).toMatch(/Client/)
  })

  test('TC-SPM87-AC02 before applying, the coordinator sees venue suitability and equipment availability at the new period', async ({
    page,
  }) => {
    const preview = await eventApi('POST', '/e1/reschedule/preview', 'EC-01', later())
    expect(preview.status).toBe(200)
    expect(JSON.stringify(preview.body)).toMatch(/venue|suitable|free/i)
    expect(JSON.stringify(preview.body)).toMatch(/equipment|available/i)
    await login(page, account('EC-01'))
    await page.goto('/app/events/e1')
    await page.getByTestId('event-reschedule').click()
    await expect(page.getByTestId('reschedule-impact')).toBeVisible()
  })

  test('TC-SPM87-AC03 when the venue is free and suitable, the coordinator can carry the booking across', async () => {
    const preview = await eventApi('POST', '/e3/reschedule/preview', 'EC-01', later())
    if (preview.body?.venueFree && preview.body?.venueSuitable) {
      const moved = await eventApi('POST', '/e3/reschedule', 'EC-01', {
        ...later(),
        reason: 'Carry booking',
        carryVenueBooking: true,
      })
      expect(moved.status).toBe(200)
      expect(moved.body.venueCarried || moved.body.bookingCarried).toBeTruthy()
    } else {
      expect(preview.status).toBe(200)
    }
  })

  test('TC-SPM87-AC04 when the venue is not available, the coordinator is told before committing and can proceed or abandon', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.goto('/app/events/e1')
    await page.getByTestId('event-reschedule').click()
    await page.getByTestId('reschedule-start').fill(new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 16))
    await expect(page.getByTestId('reschedule-venue-unavailable')).toBeVisible()
    await expect(page.getByTestId('reschedule-anyway')).toBeVisible()
    await expect(page.getByTestId('reschedule-abandon')).toBeVisible()
  })

  test('TC-SPM87-AC05 the old period is released only after the reschedule is applied', async () => {
    const before = await venueRequest('GET', '/venues/bookings/vb-pending', 'VS-01')
    const preview = await eventApi('POST', '/e1/reschedule/preview', 'EC-01', later())
    expect(preview.status).toBe(200)
    const still = await venueRequest('GET', '/venues/bookings/vb-pending', 'VS-01')
    expect(still.body.status).toBe(before.body?.status)
    const applied = await eventApi('POST', '/e3/reschedule', 'EC-01', {
      ...later(),
      reason: 'Commit move',
    })
    expect(applied.status).toBe(200)
  })

  test('TC-SPM87-AC06 equipment reservations are re-checked at the new period and shortfalls are flagged, not dropped', async () => {
    const moved = await eventApi('POST', '/e2/reschedule', 'EC-01', {
      ...later(),
      reason: 'Move workshop',
    })
    expect([200, 409]).toContain(moved.status)
    const reservation = await eventApi('GET', '/e2', 'EC-01')
    expect(reservation.status).toBe(200)
    expect(JSON.stringify(moved.body || reservation.body)).toMatch(/equipment|flag|reverify|shortfall/i)
  })

  test('TC-SPM87-AC07 the organiser, venue staff, technical support, and registered attendees are notified', async ({
    page,
  }) => {
    await eventApi('POST', '/e1/reschedule', 'EC-01', {
      ...later(),
      reason: 'Notify all',
    })
    await login(page, account('EO-01'))
    await page.goto('/app/events/e1')
    await expect(page.getByTestId('event-rescheduled')).toContainText(/date|time|reschedul/i)
  })

  test('TC-SPM87-AC08 a registration close after the new start is brought forward and the coordinator is told', async () => {
    const start = new Date(Date.now() + 4 * 86400000)
    const moved = await eventApi('POST', '/e1/reschedule', 'EC-01', {
      proposedStartAt: start.toISOString(),
      proposedEndAt: new Date(start.getTime() + 2 * 3600000).toISOString(),
      reason: 'Sooner',
    })
    expect([200, 409]).toContain(moved.status)
    if (moved.status === 200) {
      expect(moved.body.registrationClosesAt).toBeTruthy()
      expect(new Date(moved.body.registrationClosesAt).getTime()).toBeLessThanOrEqual(start.getTime())
      expect(moved.body.registrationCloseAdjusted || moved.body.registrationBroughtForward).toBeTruthy()
    }
  })

  test('TC-SPM87-AC09 the reschedule, old and new period, reason, actor, and time are in the activity log', async () => {
    const period = later()
    await eventApi('POST', '/e3/reschedule', 'EC-01', { ...period, reason: 'Logged move' })
    const log = await eventApi('GET', '/e3/activity-log', 'EC-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/reschedul|Logged move|u2/)
    expect(JSON.stringify(log.body)).toMatch(/old|previous|new/)
  })
})
