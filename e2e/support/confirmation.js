import { expect } from '@playwright/test'
import { bearer } from './auth.js'
import { newEventPayload, venuePeriod } from './api-data.js'
import { assignCoordinator, eventUrl } from './event.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './venue-request.js'
import { venueRequest, venueToken } from './venue.js'

// SPM-72 and SPM-121: an event's path from planning through the safety review to Confirmed.

const CROWD = 'Guests enter by the lift lobby and leave by the promenade doors; aisles stay 2 m wide.'

// A 10:00 to 12:00 UTC slot on a random day among a million, starting 11
// years ahead. These events book the venue for their own time, so they keep
// clear of the days freshPeriod() uses and of each other's leftover bookings
// across reruns.
export function distantPeriod() {
  return venuePeriod(4000 + Math.floor(Math.random() * 1_000_000))
}

// Event-service calls that sign each account in once and reuse the token, to
// stay inside Firebase's sign-in quota across the many calls each test makes.
export async function events(method, path, accountId, body) {
  const response = await fetch(eventUrl(path), {
    method,
    headers: { ...bearer(await venueToken(accountId)), 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

// A planning event of its own (Theatre, 50 people, assigned to EC-01) on a
// fresh day, so no seeded event changes and its venue can be booked for its own time.
export async function planningEvent(label, extras = {}) {
  const period = distantPeriod()
  const event = await approvedEvent({
    ...THEATRE_EVENT,
    eventName: `AUTO-${label}-${Date.now()}`,
    proposedStartAt: period.startsAt,
    proposedEndAt: period.endsAt,
    ...extras,
  })
  return { ...event, period }
}

// The same, with one projector (eq1) on the event. Equipment lines are set at
// draft stage, so the organiser saves a draft, submits it, and EC-01 approves it.
export async function planningEventWithEquipment(label) {
  const period = distantPeriod()
  const { registrationEnabled, capacity, ...fields } = newEventPayload(`AUTO-${label}-${Date.now()}`)
  const draft = await events('POST', '/drafts', 'EO-01', {
    ...fields,
    ...THEATRE_EVENT,
    proposedStartAt: period.startsAt,
    proposedEndAt: period.endsAt,
    equipmentLines: [{ equipmentId: 'eq1', quantity: 1 }],
  })
  expect(draft.status, JSON.stringify(draft.body)).toBe(201)
  const submitted = await events('POST', `/${draft.body.eventId}/submit`, 'EO-01')
  expect(submitted.status, JSON.stringify(submitted.body)).toBe(200)
  await assignCoordinator(draft.body.eventId, 'u2')
  const approved = await events('POST', `/${draft.body.eventId}/approve`, 'EC-01', {})
  expect(approved.status, JSON.stringify(approved.body)).toBe(200)
  return { ...approved.body, period }
}

// EC-01 requests a venue, by default Marina Hall A for the event's own time.
export async function requestBooking(event, venueId = 'v1', period = event.period) {
  const requested = await requestVenue(event, venueId, period)
  expect(requested.status, JSON.stringify(requested.body)).toBe(201)
  return requested.body
}

export async function approveBooking(booking) {
  const approved = await venueRequest('POST', `/venues/bookings/${booking.bookingId}/approve`, 'VS-01', {
    reason: 'AUTO-confirmation',
  })
  expect(approved.status, JSON.stringify(approved.body)).toBe(200)
  return approved.body
}

// Venue staff approve a booking, by default Marina Hall A for the event's own time.
export async function bookVenue(event, period = event.period, venueId = 'v1') {
  return approveBooking(await requestBooking(event, venueId, period))
}

// SPM-120: the coordinator submits the plan. Reserved equipment needs a
// placement; it is ignored when there is none.
export function submitSafetyReview(event) {
  return events('POST', `/${event.eventId}/safety-reviews`, 'EC-01', {
    crowdMovement: CROWD,
    equipmentPlacement: 'Projector on the lectern, cables taped along the stage edge.',
  })
}

export function decideSafetyReview(event, review, action, body = {}) {
  return events('POST', `/${event.eventId}/safety-reviews/${review.reviewId}/${action}`, 'SO-01', body)
}

// The coordinator submits the plan and the Safety Officer approves it.
export async function passSafetyReview(event) {
  const submitted = await submitSafetyReview(event)
  expect(submitted.status, JSON.stringify(submitted.body)).toBe(201)
  const approved = await decideSafetyReview(event, submitted.body, 'approve')
  expect(approved.status, JSON.stringify(approved.body)).toBe(200)
}

export async function readyToConfirm(label, extras) {
  const event = await planningEvent(label, extras)
  await bookVenue(event)
  await passSafetyReview(event)
  return event
}

export function confirmation(event) {
  return events('GET', `/${event.eventId}/confirmation`, 'EC-01')
}

export function confirm(event, accountId = 'EC-01') {
  return events('POST', `/${event.eventId}/confirm`, accountId)
}
