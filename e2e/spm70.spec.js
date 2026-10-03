import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venueBookingPayload } from './support/api-data.js'
import { assignCoordinator, createSubmittedEvent, eventApi } from './support/event.js'
import { venueRequest } from './support/venue.js'

async function underReviewEvent() {
  const event = await createSubmittedEvent('EO-01', `AUTO-SPM70-${Date.now()}`)
  await assignCoordinator(event.eventId, 'u2', 'EC-01')
  return event.eventId
}

test.describe('SPM-70 Reject a submitted request with a reason', () => {
  test('TC-SPM70-AC01 the assigned coordinator can reject Under Review or Changes Requested', async () => {
    const eventId = await underReviewEvent()
    const rejected = await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'outside ConnectSphere services',
      explanation: 'Not a venue we support.',
    })
    expect(rejected.status).toBe(200)
    expect(rejected.body.status).toMatch(/rejected/i)
  })

  test('TC-SPM70-AC02 a reason is mandatory from the published list, with a free-text explanation', async () => {
    const eventId = await underReviewEvent()
    const missing = await eventApi('POST', `/${eventId}/reject`, 'EC-01', {})
    expect([400, 422]).toContain(missing.status)
    const rejected = await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'no suitable venue available',
      explanation: 'No hall fits the dates.',
    })
    expect(rejected.status).toBe(200)
    expect(rejected.body.decisionReason || rejected.body.reason).toMatch(/venue/)
    expect(rejected.body.explanation).toMatch(/hall/)
  })

  test('TC-SPM70-AC03 rejecting moves the event to Rejected, which is terminal', async () => {
    const eventId = await underReviewEvent()
    await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'insufficient notice',
      explanation: 'Too late',
    })
    const approve = await eventApi('POST', `/${eventId}/approve`, 'EC-01', {})
    expect([400, 409]).toContain(approve.status)
    const stored = await eventApi('GET', `/${eventId}`, 'EC-01')
    expect(stored.body.status).toMatch(/rejected/i)
  })

  test('TC-SPM70-AC04 the organiser is notified and can see the reason and explanation', async ({
    page,
  }) => {
    const eventId = await underReviewEvent()
    await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'insufficient equipment',
      explanation: 'LED wall unavailable',
    })
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${eventId}`)
    await expect(page.getByTestId('organiser-decision')).toContainText(/rejected|insufficient equipment|LED/i)
  })

  test('TC-SPM70-AC05 rejecting releases venue and equipment holds', async () => {
    const eventId = await underReviewEvent()
    const booking = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      ...venueBookingPayload(290, eventId, 'v2'),
    })
    expect(booking.status).toBe(201)
    await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'outside ConnectSphere services',
      explanation: 'Released',
    })
    const viewed = await venueRequest('GET', `/venues/bookings/${booking.body.bookingId}`, 'VS-01')
    expect(viewed.body.status).toMatch(/released|withdrawn|rejected|cancelled/i)
  })

  test('TC-SPM70-AC06 the rejected event stays in organiser history and the activity log', async () => {
    const eventId = await underReviewEvent()
    await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'insufficient notice',
      explanation: 'Keep history',
    })
    const list = await eventApi('GET', '', 'EO-01')
    expect((list.body || []).map((row) => row.eventId)).toContain(eventId)
    const log = await eventApi('GET', `/${eventId}/activity-log`, 'EO-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/reject/)
  })

  test('TC-SPM70-AC07 the organiser can create a fresh request after a rejection', async () => {
    const eventId = await underReviewEvent()
    await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'outside ConnectSphere services',
      explanation: 'Try again',
    })
    const fresh = await createSubmittedEvent('EO-01', 'AUTO-SPM70-fresh')
    expect(fresh.eventId).not.toBe(eventId)
    expect(fresh.status).toMatch(/submitted/i)
  })
})
