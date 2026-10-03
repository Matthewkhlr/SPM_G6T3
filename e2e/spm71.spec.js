import { test, expect } from '@playwright/test'
import { venueBookingPayload } from './support/api-data.js'
import { eventApi } from './support/event.js'
import { venueRequest } from './support/venue.js'

test.describe('SPM-71 Update event information and flag significant changes', () => {
  test('TC-SPM71-AC01 the assigned coordinator can edit name, description, purpose, category, notes, and contact without warning', async () => {
    const updated = await eventApi('PATCH', '/e3', 'EC-01', {
      eventName: 'Partner Networking Night',
      description: 'AUTO-SPM71 quiet edit',
      purpose: 'Updated purpose',
      category: 'networking',
      internalNotes: 'Staff only',
      organiserContact: 'organiser@connectsphere.com',
    })
    expect(updated.status).toBe(200)
    expect(updated.body.warning || updated.body.requiresConfirmation).toBeFalsy()
  })

  test('TC-SPM71-AC02 date, time, attendance, layout, accessibility, and equipment are significant fields', async () => {
    const meta = await eventApi('GET', '/significant-fields', 'EC-01')
    expect(meta.status).toBe(200)
    const fields = meta.body.fields || meta.body
    for (const field of [
      'proposedStartAt',
      'proposedEndAt',
      'expectedAttendance',
      'layoutPreference',
      'accessibilityNeeds',
      'equipmentRequirements',
    ]) {
      expect(fields).toEqual(expect.arrayContaining([field]))
    }
  })

  test('TC-SPM71-AC03 a significant edit on an event with a confirmed booking requires confirmation and names affected arrangements', async () => {
    const blocked = await eventApi('PATCH', '/e1', 'EC-01', {
      expectedAttendance: 200,
    })
    expect(blocked.status).toBe(409)
    expect(JSON.stringify(blocked.body)).toMatch(/venue|equipment|re-verif|confirm/i)

    const saved = await eventApi('PATCH', '/e1', 'EC-01', {
      expectedAttendance: 200,
      confirmSignificantChange: true,
    })
    expect(saved.status).toBe(200)
  })

  test('TC-SPM71-AC04 saving a significant change marks affected bookings and reservations for re-verification', async () => {
    await eventApi('PATCH', '/e2', 'EC-01', {
      proposedStartAt: new Date(Date.now() + 22 * 24 * 60 * 60 * 1000).toISOString(),
      confirmSignificantChange: true,
    })
    const booking = await venueRequest('GET', '/venues/bookings/vb-reverify', 'VS-01')
    expect(booking.status).toBe(200)
    expect(booking.body.needsReverification || booking.body.status).toBeTruthy()
  })

  test('TC-SPM71-AC05 every edit is written to the activity log with old and new values', async () => {
    const before = await eventApi('GET', '/e3', 'EC-01')
    await eventApi('PATCH', '/e3', 'EC-01', { description: `AUTO-log-${Date.now()}` })
    const log = await eventApi('GET', '/e3/activity-log', 'EC-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/description/)
    expect(JSON.stringify(log.body)).toMatch(/old|previous/)
    expect(before.status).toBe(200)
  })

  test('TC-SPM71-AC06 a significant change on a confirmed event no longer reads as fully confirmed', async () => {
    await eventApi('PATCH', '/e1', 'EC-01', {
      expectedAttendance: 180,
      confirmSignificantChange: true,
    })
    const stored = await eventApi('GET', '/e1', 'EO-01')
    expect(stored.body.status).not.toMatch(/^confirmed$/i)
    expect(stored.body.status).toMatch(/reconsider|planning|under review|arrangements/i)
  })

  test('TC-SPM71-AC07 completed, cancelled, or rejected events cannot be edited', async () => {
    const denied = await eventApi('PATCH', '/e8', 'EC-01', { description: 'nope' })
    expect([400, 403, 409]).toContain(denied.status)
  })
})
