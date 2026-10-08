import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { equipmentApi } from './support/equipment.js'
import {
  approveBooking,
  bookVenue,
  confirm,
  confirmation,
  decideSafetyReview,
  events,
  passSafetyReview,
  planningEvent,
  planningEventWithEquipment,
  requestBooking,
  submitSafetyReview,
} from './support/confirmation.js'

const DAY = 24 * 60 * 60 * 1000

async function underSafetyReview(label) {
  const event = await planningEvent(label)
  await bookVenue(event)
  const submitted = await submitSafetyReview(event)
  expect(submitted.status, JSON.stringify(submitted.body)).toBe(201)
  return { event, review: submitted.body }
}

async function statusOf(event) {
  return (await events('GET', `/${event.eventId}`, 'EC-01')).body.status
}

// What an attendee can browse, and the confirmed list anyone can read.
async function visibleToAttendees(event) {
  const open = (await events('GET', '/open-for-registration', 'ATT-01')).body.map((row) => row.eventId)
  const confirmed = (await events('GET', '/confirmed', 'ATT-01')).body.map((row) => row.eventId)
  return open.includes(event.eventId) || confirmed.includes(event.eventId)
}

// The safety part of what Confirm is waiting on, if anything.
async function safetyGap(event) {
  const check = await confirmation(event)
  expect(check.status, JSON.stringify(check.body)).toBe(200)
  return check.body.missing.find((gap) => gap.kind === 'safety')?.message
}

async function openMyEvents(page) {
  await page.locator('.nav-item').getByText('My Events', { exact: true }).click()
  await expect(page.getByTestId('organiser-event-list')).toBeVisible()
}

test.describe('SPM-121 Preparation stays blocked until the Safety Officer approves the event', () => {
  test('TC-SPM121-AC01 an approved venue booking and reserved equipment confirm the arrangements without making the event Confirmed or visible to attendees', async () => {
    const now = Date.now()
    const event = await planningEvent('SPM121-ac01', {
      registrationEnabled: true,
      registrationOpensAt: new Date(now - DAY).toISOString(),
      registrationClosesAt: new Date(now + 60 * DAY).toISOString(),
    })
    await bookVenue(event)
    const requested = await equipmentApi('POST', '/equipment/requests', 'EC-01', {
      eventId: event.eventId,
      equipmentId: 'eq1',
      quantity: 1,
      technicalRequirements: 'AUTO-SPM121 HDMI to the lectern',
      startsAt: event.period.startsAt,
      endsAt: event.period.endsAt,
    })
    expect(requested.status, JSON.stringify(requested.body)).toBe(201)
    const reviewed = await equipmentApi('POST', `/equipment/requests/${requested.body.requestId}/review`, 'TS-01', {
      approve: true,
      reviewNote: 'AUTO-SPM121',
    })
    expect(reviewed.status, JSON.stringify(reviewed.body)).toBe(200)
    const reserved = await equipmentApi('POST', `/equipment/requests/${requested.body.requestId}/reserve`, 'TS-01')
    expect(reserved.status, JSON.stringify(reserved.body)).toBe(201)

    // The venue and equipment are confirmed: only the safety review is outstanding.
    const check = await confirmation(event)
    expect(check.body.missing.map((gap) => gap.kind)).toEqual(['safety'])
    expect(await statusOf(event)).toBe('planning')
    expect(await visibleToAttendees(event)).toBe(false)

    await passSafetyReview(event)
    expect(await statusOf(event)).toBe('safety approved')
    expect(await visibleToAttendees(event)).toBe(false)
  })

  test('TC-SPM121-AC02 the safety review starts only once every requested venue is approved and every equipment line is reserved or recorded as not required', async () => {
    const event = await planningEventWithEquipment('SPM121-ac02')
    await bookVenue(event)
    const second = await requestBooking(event, 'v3')

    let refused = await submitSafetyReview(event)
    expect(refused.status).toBe(409)
    expect(refused.body.detail.missing).toEqual(['venue', 'equipment'])
    expect(refused.body.detail.message).toContain('have not approved the booking at')

    await approveBooking(second)
    refused = await submitSafetyReview(event)
    expect(refused.status).toBe(409)
    expect(refused.body.detail.missing).toEqual(['equipment'])
    expect(await statusOf(event)).toBe('planning')

    const marked = await events('POST', `/${event.eventId}/equipment-lines/eq1/not-required`, 'EC-01', {
      reason: 'The venue has a built-in projector.',
    })
    expect(marked.status, JSON.stringify(marked.body)).toBe(200)
    const submitted = await submitSafetyReview(event)
    expect(submitted.status, JSON.stringify(submitted.body)).toBe(201)
    expect(await statusOf(event)).toBe('safety review')
  })

  test('TC-SPM121-AC03 the event moves to Confirmed only after the Safety Officer approves', async () => {
    const { event, review } = await underSafetyReview('SPM121-ac03')
    const early = await confirm(event)
    expect(early.status).toBe(409)
    expect(early.body.detail.missing).toEqual(['safety'])
    expect(await statusOf(event)).toBe('safety review')

    const approved = await decideSafetyReview(event, review, 'approve')
    expect(approved.status, JSON.stringify(approved.body)).toBe(200)
    expect(await statusOf(event)).toBe('safety approved')

    const confirmed = await confirm(event)
    expect(confirmed.status, JSON.stringify(confirmed.body)).toBe(200)
    expect(confirmed.body.status).toBe('confirmed')
  })

  test('TC-SPM121-AC04 confirm is unavailable while the safety check is outstanding, rejected, or returned for changes', async ({
    page,
  }) => {
    const { event, review } = await underSafetyReview('SPM121-ac04')
    expect(await safetyGap(event)).toBe('The Safety Officer has not reviewed it yet.')
    expect((await confirm(event)).status).toBe(409)

    const rejected = await decideSafetyReview(event, review, 'reject', { reason: 'Stage blocks fire exit B.' })
    expect(rejected.status, JSON.stringify(rejected.body)).toBe(200)
    expect(await safetyGap(event)).toContain('was rejected: Stage blocks fire exit B.')
    expect((await confirm(event)).status).toBe(409)

    const again = await submitSafetyReview(event)
    expect(again.status, JSON.stringify(again.body)).toBe(201)
    const changes = await decideSafetyReview(event, again.body, 'request-changes', {
      requiredChanges: 'Widen the aisles to 3 m.',
    })
    expect(changes.status, JSON.stringify(changes.body)).toBe(200)
    expect(await safetyGap(event)).toContain('asked for changes: Widen the aisles to 3 m.')
    expect((await confirm(event)).status).toBe(409)

    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await expect(page.getByTestId('confirm-missing')).toContainText('asked for changes: Widen the aisles to 3 m.')
    await expect(page.getByTestId('event-confirm')).toHaveCount(0)
  })

  test('TC-SPM121-AC05 the organiser can see the event is waiting on the safety review or has had safety changes requested', async ({
    page,
  }) => {
    const { event, review } = await underSafetyReview('SPM121-ac05')
    await login(page, account('EO-01'))
    await openMyEvents(page)
    await expect(page.getByTestId(`organiser-event-${event.eventId}-status`)).toHaveText('Waiting on safety review')
    await expect(page.getByTestId(`organiser-event-${event.eventId}-safety`)).toHaveCount(0)

    const changes = await decideSafetyReview(event, review, 'request-changes', {
      requiredChanges: 'Widen the aisles to 3 m.',
    })
    expect(changes.status, JSON.stringify(changes.body)).toBe(200)
    await page.reload()
    await openMyEvents(page)
    await expect(page.getByTestId(`organiser-event-${event.eventId}-safety`)).toHaveText('Safety changes requested')

    await page.getByTestId(`organiser-event-${event.eventId}`).click()
    await expect(page.getByTestId('safety-outcome')).toContainText('Widen the aisles to 3 m.')
  })
})
