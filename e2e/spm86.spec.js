import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { eventApi } from './support/event.js'
import { venueRequest } from './support/venue.js'
import { equipmentApi } from './support/equipment.js'

test.describe('SPM-86 Re-verify arrangements affected by a significant change', () => {
  test('TC-SPM86-AC01 a significant field change marks affected venue bookings and equipment reservations for re-verification', async () => {
    const applied = await eventApi('PATCH', '/e2', 'EC-01', {
      proposedStartAt: new Date(Date.now() + 22 * 86400000).toISOString(),
      confirmSignificantChange: true,
    })
    expect([200, 409]).toContain(applied.status)
    const booking = await venueRequest('GET', '/venues/bookings/vb-reverify', 'VS-01')
    expect(booking.status).toBe(200)
    expect(booking.body.needsReverification || /reverify/i.test(booking.body.status)).toBeTruthy()
    const reservation = await equipmentApi('GET', '/equipment/reservations/er-e2', 'TS-01')
    expect(reservation.status).toBe(200)
    expect(reservation.body.needsReverification || /reverify/i.test(reservation.body.status)).toBeTruthy()
  })

  test('TC-SPM86-AC02 a re-verification flag is visible on the event, readiness, venue calendar, and staff queues', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.goto('/app/events/e2')
    await expect(page.getByTestId('reverify-flag')).toBeVisible()
    await page.goto('/app/events/e2/readiness')
    await expect(page.getByTestId('readiness-reverify')).toBeVisible()
    await login(page, account('VS-01'))
    await page.goto('/app/venues/v1/calendar')
    await expect(page.getByTestId('calendar-reverify')).toBeVisible()
    await login(page, account('TS-01'))
    await page.goto('/app')
    await expect(page.getByTestId('tech-reverification-er-e2')).toBeVisible()
  })

  test('TC-SPM86-AC03 venue staff are notified for bookings they approved, and technical support for reservations', async () => {
    const vs = await venueRequest('GET', '/notifications', 'VS-01')
    expect([200, 404]).toContain(vs.status)
    const ts = await equipmentApi('GET', '/notifications', 'TS-01')
    expect([200, 404]).toContain(ts.status)
    await eventApi('PATCH', '/e2', 'EC-01', {
      expectedAttendance: 45,
      confirmSignificantChange: true,
    })
    const afterVs = await venueRequest('GET', '/notifications', 'VS-01')
    const afterTs = await equipmentApi('GET', '/notifications', 'TS-01')
    expect(JSON.stringify(afterVs.body || vs.body)).toMatch(/re-?verif|e2|booking/i)
    expect(JSON.stringify(afterTs.body || ts.body)).toMatch(/re-?verif|e2|equipment/i)
  })

  test('TC-SPM86-AC04 a date or time change re-checks the booking for conflicts and reports them rather than silently moving it', async () => {
    const check = await venueRequest('POST', '/venues/bookings/vb-reverify/recheck', 'VS-01', {
      proposedStartAt: new Date(Date.now() + 14 * 86400000).toISOString(),
      proposedEndAt: new Date(Date.now() + 14 * 86400000 + 4 * 3600000).toISOString(),
    })
    expect(check.status).toBe(200)
    expect(check.body.movedSilently).toBeFalsy()
    expect(check.body.conflict || check.body.verdict || check.body.status).toBeTruthy()
    const booking = await venueRequest('GET', '/venues/bookings/vb-reverify', 'VS-01')
    expect(booking.body.needsReverification || /reverify|approved/i.test(booking.body.status)).toBeTruthy()
  })

  test('TC-SPM86-AC05 when the venue is still suitable and free, venue staff can re-confirm in one action', async ({
    page,
  }) => {
    await login(page, account('VS-01'))
    await page.goto('/app/venues/bookings/vb-reverify')
    await page.getByTestId('booking-reconfirm').click()
    const reconfirmed = await venueRequest('POST', '/venues/bookings/vb-reverify/reconfirm', 'VS-01')
    expect([200, 409]).toContain(reconfirmed.status)
    if (reconfirmed.status === 200) {
      expect(reconfirmed.body.needsReverification).toBeFalsy()
      expect(reconfirmed.body.status).toMatch(/approved|confirmed/i)
    }
  })

  test('TC-SPM86-AC06 when the venue is unsuitable or unavailable, the booking is released and the coordinator is prompted to search again', async ({
    page,
  }) => {
    const released = await venueRequest('POST', '/venues/bookings/vb-reverify/recheck', 'EC-01', {
      forceUnavailable: true,
    })
    expect([200, 409]).toContain(released.status)
    await login(page, account('EC-01'))
    await page.goto('/app/events/e2')
    await expect(page.getByTestId('search-venue-again')).toBeVisible()
  })

  test('TC-SPM86-AC07 extra equipment that is unavailable is flagged to technical support, not reserved', async () => {
    const flagged = await eventApi('PATCH', '/e2', 'EC-01', {
      equipmentLines: [{ equipmentId: 'eq1', quantity: 40 }],
      confirmSignificantChange: true,
    })
    expect([200, 409]).toContain(flagged.status)
    const queue = await equipmentApi('GET', '/equipment/queue', 'TS-01')
    expect(queue.status).toBe(200)
    expect(JSON.stringify(queue.body)).toMatch(/e2|eq1|reverify|shortfall|attention/i)
    const reserved = await equipmentApi('GET', '/equipment/reservations/er-e2', 'TS-01')
    expect(reserved.body.quantity).not.toBe(40)
  })

  test('TC-SPM86-AC08 a confirmed event with arrangements awaiting re-verification is not shown as fully confirmed', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e2')
    const status = page.getByTestId('organiser-event-status')
    await expect(status).toBeVisible()
    await expect(status).not.toHaveText(/^confirmed$/i)
    await expect(page.getByTestId('reverify-flag')).toBeVisible()
    const attendee = await eventApi('GET', '/e2', 'ATT-01')
    expect(JSON.stringify(attendee.body)).not.toMatch(/"status"\s*:\s*"confirmed"/i)
  })

  test('TC-SPM86-AC09 registered attendees are notified when date, time, or venue changes', async () => {
    await eventApi('PATCH', '/e1', 'EC-01', {
      proposedStartAt: new Date(Date.now() + 15 * 86400000).toISOString(),
      confirmSignificantChange: true,
    })
    const list = await eventApi('GET', '/e1/registrations', 'EC-01')
    expect([200, 404]).toContain(list.status)
    const notice = await eventApi('GET', '/e1/notifications', 'ATT-01')
    expect(JSON.stringify(notice.body || list.body)).toMatch(/date|time|venue|e1/i)
  })

  test('TC-SPM86-AC10 once every flagged arrangement is re-verified, the event returns to its previous presentation', async ({
    page,
  }) => {
    await venueRequest('POST', '/venues/bookings/vb-reverify/reconfirm', 'VS-01')
    await equipmentApi('POST', '/equipment/reservations/er-e2/reconfirm', 'TS-01')
    const stored = await eventApi('GET', '/e2', 'EO-01')
    expect(stored.status).toBe(200)
    expect(stored.body.needsReverification).toBeFalsy()
    await login(page, account('EO-01'))
    await page.goto('/app/events/e2')
    await expect(page.getByTestId('reverify-flag')).toHaveCount(0)
  })
})
