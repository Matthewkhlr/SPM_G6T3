import { expect } from '@playwright/test'
import { assignCoordinator, eventApi } from './event.js'
import { newEventPayload, venuePeriod } from './api-data.js'
import { venueRequest } from './venue.js'

// A Theatre event that suits Marina Hall A (v1) and Exhibition Hall B (v3),
// both open every day, so a weekday or weekend date never matters.
export const THEATRE_EVENT = { layoutPreference: 'Theatre', expectedAttendance: 50, venueRequirements: 'Stage.' }

// SPM-63 AC1: only the assigned coordinator may request a venue, and only for
// an event approved for planning. Each test makes its own such event, assigned
// to EC-01 (u2). SPM-114 allows several venues on that event; a second live
// booking of the same venue is still refused.
export async function approvedEvent(overrides = {}) {
  const created = await eventApi('POST', '', 'EO-01', {
    ...newEventPayload(`VENUE-REQ-${Date.now()}`),
    ...overrides,
  })
  expect(created.status, JSON.stringify(created.body)).toBe(201)
  await assignCoordinator(created.body.eventId, 'u2')
  const approved = await eventApi('POST', `/${created.body.eventId}/approve`, 'EC-01', {})
  expect(approved.status, JSON.stringify(approved.body)).toBe(200)
  return approved.body
}

// A 10:00 to 12:00 UTC slot on a random day years ahead, so a rerun rarely
// meets a booking an earlier run left behind. The days span about 80 years:
// earlier runs leave confirmed bookings on seeded venues such as v1, and over a
// shorter span a new request often landed on one of those days and was refused.
export function freshPeriod(hours = 2) {
  return venuePeriod(300 + Math.floor(Math.random() * 30000), hours)
}

export function requestVenue(event, venueId, period = freshPeriod(), extras = {}) {
  return venueRequest('POST', '/venues/bookings', 'EC-01', {
    eventId: event.eventId,
    venueId,
    ...period,
    requirementsSnapshot: `AUTO-${Date.now()}`,
    ...extras,
  })
}
