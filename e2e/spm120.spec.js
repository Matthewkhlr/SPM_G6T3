import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { eventApi } from './support/event.js'
import { notificationApi } from './support/registration.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './support/venue-request.js'
import { distantPeriod } from './support/confirmation.js'
import { venueRequest } from './support/venue.js'

const CROWD = 'Guests enter by the lift lobby and leave by the promenade doors; aisles stay 2 m wide.'

// A planning event of its own (Theatre, 50 people) so no seeded event changes.
// It is held on a distant day, so its venue booking can be for the event's own time.
async function planningEvent(label) {
  const period = distantPeriod()
  const event = await approvedEvent({
    ...THEATRE_EVENT,
    eventName: `AUTO-SPM120-${label}-${Date.now()}`,
    proposedStartAt: period.startsAt,
    proposedEndAt: period.endsAt,
  })
  return { ...event, period }
}

// Venue staff confirm a Marina Hall A booking for the event's date and time
// (SPM-72 AC1). The event needs no equipment, so its technical arrangements
// have nothing left to confirm.
async function confirmVenue(event) {
  const requested = await requestVenue(event, 'v1', event.period)
  expect(requested.status, JSON.stringify(requested.body)).toBe(201)
  const approved = await venueRequest('POST', `/venues/bookings/${requested.body.bookingId}/approve`, 'VS-01', {
    reason: 'AUTO-SPM120',
  })
  expect(approved.status, JSON.stringify(approved.body)).toBe(200)
  return requested.body
}

function submit(event) {
  return eventApi('POST', `/${event.eventId}/safety-reviews`, 'EC-01', { crowdMovement: CROWD })
}

async function underSafetyReview(label) {
  const event = await planningEvent(label)
  await confirmVenue(event)
  const submitted = await submit(event)
  expect(submitted.status, JSON.stringify(submitted.body)).toBe(201)
  return { event, review: submitted.body }
}

function decide(event, review, action, accountId, body) {
  return eventApi('POST', `/${event.eventId}/safety-reviews/${review.reviewId}/${action}`, accountId, body)
}

test.describe('SPM-120 Safety review after venue and technical arrangements are confirmed', () => {
  test('TC-SPM120-AC01 the review is available only after the venue and technical arrangements are confirmed', async () => {
    const event = await planningEvent('ac01')
    const early = await submit(event)
    expect(early.status).toBe(409)
    expect(early.body.detail.missing).toContain('venue')

    await confirmVenue(event)
    const submitted = await submit(event)
    expect(submitted.status, JSON.stringify(submitted.body)).toBe(201)
    expect(submitted.body.status).toBe('pending')
    const stored = await eventApi('GET', `/${event.eventId}`, 'EC-01')
    expect(stored.body.status).toBe('safety review')
  })

  test('TC-SPM120-AC02 the Safety Officer sees attendance, venue capacity and layout, emergency access, accessibility, equipment placement, crowd movement, and restrictions', async ({
    page,
  }) => {
    const { event } = await underSafetyReview('ac02')
    const [review] = (await eventApi('GET', `/${event.eventId}/safety-reviews`, 'SO-01')).body
    const venue = review.package.venues[0]
    expect(review.package.expectedAttendance).toBe(50)
    expect(venue.venueName).toBe('Marina Hall A')
    expect(venue.layout).toBe('Theatre')
    expect(venue.capacityInLayout).toBeGreaterThan(0)
    expect(venue.emergencyAccess).toMatch(/exit/i)
    expect(venue.restrictions).toBeTruthy()
    expect(review.package.crowdMovement).toBe(CROWD)

    await login(page, account('SO-01'))
    await page.goto(`/app/events/${event.eventId}`)
    const shown = page.getByTestId('safety-package')
    await expect(shown).toContainText('Marina Hall A')
    await expect(page.getByTestId('safety-venue-capacity')).toContainText('Theatre')
    await expect(page.getByTestId('safety-emergency-access')).toContainText(/exit/i)
    await expect(page.getByTestId('safety-restrictions')).not.toBeEmpty()
    await expect(page.getByTestId('safety-accessibility')).toBeVisible()
    await expect(page.getByTestId('safety-placement')).toBeVisible()
    await expect(page.getByTestId('safety-crowd')).toContainText('promenade doors')
  })

  test('TC-SPM120-AC03 AC04 approving through the review records the decision, the officer, and the time', async ({
    page,
  }) => {
    const { event } = await underSafetyReview('ac04')
    await login(page, account('SO-01'))
    await page.goto(`/app/events/${event.eventId}`)
    const decision = page.waitForResponse(
      (response) => /\/safety-reviews\/[^/]+\/approve$/.test(response.url()) && response.request().method() === 'POST',
    )
    await page.getByTestId('safety-approve').click()
    expect((await decision).status()).toBe(200)
    await expect(page.getByTestId('safety-outcome')).toContainText(/coordinator can now confirm/i)

    const [review] = (await eventApi('GET', `/${event.eventId}/safety-reviews`, 'EC-01')).body
    expect(review.status).toBe('approved')
    expect(review.decidedBy).toBe('u13')
    expect(review.decidedAt).toBeTruthy()
    const stored = await eventApi('GET', `/${event.eventId}`, 'EC-01')
    expect(stored.body.status).toBe('safety approved')
  })

  test('TC-SPM120-AC05 AC09 rejecting records the reason, keeps the event out of preparation without cancelling it, notifies both sides, and allows a new check', async () => {
    const { event, review } = await underSafetyReview('ac05')
    const missingReason = await decide(event, review, 'reject', 'SO-01', {})
    expect(missingReason.status).toBe(422)

    const rejected = await decide(event, review, 'reject', 'SO-01', { reason: 'Stage blocks fire exit B.' })
    expect(rejected.status, JSON.stringify(rejected.body)).toBe(200)
    expect(rejected.body.decisionNote).toBe('Stage blocks fire exit B.')
    const stored = await eventApi('GET', `/${event.eventId}`, 'EC-01')
    expect(stored.body.status).toBe('planning')

    for (const accountId of ['EC-01', 'EO-01']) {
      const inbox = await notificationApi('GET', '/notifications', accountId)
      expect(JSON.stringify(inbox.body), accountId).toContain(`${event.eventName} did not pass its safety review`)
    }

    const again = await submit(event)
    expect(again.status, JSON.stringify(again.body)).toBe(201)
    const history = (await eventApi('GET', `/${event.eventId}/safety-reviews`, 'EO-01')).body
    expect(history.map((row) => row.status)).toEqual(['pending', 'rejected'])
  })

  test('TC-SPM120-AC06 requesting changes records what must change, returns the event to planning, and flags the venue to be reviewed again', async () => {
    const { event, review } = await underSafetyReview('ac06')
    const changed = await decide(event, review, 'request-changes', 'SO-01', {
      requiredChanges: 'Widen the aisles to 3 m.',
      affected: ['venue'],
    })
    expect(changed.status, JSON.stringify(changed.body)).toBe(200)
    expect(changed.body.decisionNote).toBe('Widen the aisles to 3 m.')
    expect(changed.body.affected).toEqual(['venue'])

    const stored = await eventApi('GET', `/${event.eventId}`, 'EC-01')
    expect(stored.body.status).toBe('planning')
    const bookings = await venueRequest('GET', `/venues/bookings?eventId=${event.eventId}&status=approved`, 'VS-01')
    expect(bookings.body[0].needsReverification).toBe(true)
    expect(bookings.body[0].reverificationNote).toContain('Widen the aisles')
  })

  test('TC-SPM120-AC03 the Safety Officer can decide from the dashboard', async ({ page }) => {
    const { event } = await underSafetyReview('dashboard')
    await login(page, account('SO-01'))
    const item = page.getByTestId(`safety-dashboard-item-${event.eventId}`)
    await expect(item).toBeVisible()
    await page.getByTestId(`safety-dashboard-review-${event.eventId}`).click()
    await expect(item).toContainText(/emergency access/i)
    await item.getByTestId('safety-dashboard-text').fill('Keep the stage clear of exit B.')
    await item.getByTestId('safety-dashboard-affected-technical').check()
    const decision = page.waitForResponse(
      (response) => /\/request-changes$/.test(response.url()) && response.request().method() === 'POST',
    )
    await item.getByTestId('safety-dashboard-request-changes').click()
    expect((await decision).status()).toBe(200)
    await expect(page.getByTestId('safety-dashboard-notice')).toContainText(/asked for changes/i)
    await expect(item).toHaveCount(0)
    await expect(page.getByTestId(`safety-dashboard-decided-${event.eventId}`)).toContainText(/changes requested/i)

    const [review] = (await eventApi('GET', `/${event.eventId}/safety-reviews`, 'EC-01')).body
    expect(review.status).toBe('changes_requested')
    expect(review.affected).toEqual(['technical'])
  })

  test('TC-SPM120-AC07 a Safety Officer signs in with the pre-created account and sees the review queue', async ({
    page,
  }) => {
    const { event } = await underSafetyReview('ac07')
    await login(page, account('SO-01'))
    await page.locator('.nav-item').getByText('Safety Reviews', { exact: true }).click()
    await expect(page.getByTestId(`safety-queue-${event.eventId}`)).toBeVisible()
  })

  test('TC-SPM120-AC08 every other role gets 403 when approving, rejecting, or requesting changes', async () => {
    const { event, review } = await underSafetyReview('ac08')
    const bodies = {
      approve: {},
      reject: { reason: 'Not allowed' },
      'request-changes': { requiredChanges: 'Not allowed' },
    }
    for (const accountId of ['EC-01', 'EO-01', 'VS-01', 'TS-01', 'ATT-01']) {
      for (const [action, body] of Object.entries(bodies)) {
        const denied = await decide(event, review, action, accountId, body)
        expect(denied.status, `${accountId} ${action}`).toBe(403)
      }
    }
    const stored = await eventApi('GET', `/${event.eventId}`, 'EC-01')
    expect(stored.body.status).toBe('safety review')
  })
})
