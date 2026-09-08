// Hardcoded events — backs the Attendee registration acceptance criteria.
// Dates are generated relative to "now" so the demo behaves correctly whenever it's opened.
const DAY = 24 * 60 * 60 * 1000
const now = Date.now()

export const events = [
  {
    id: 'e1',
    name: 'AI in Events Summit',
    status: 'confirmed',
    registrationEnabled: true,
    registrationOpensAt: new Date(now - 5 * DAY).toISOString(),
    registrationClosesAt: new Date(now + 3 * DAY).toISOString(),
    capacity: 3,
    registeredCount: 1
  },
  {
    id: 'e2',
    name: 'Venue Ops Workshop',
    status: 'confirmed',
    registrationEnabled: true,
    registrationOpensAt: new Date(now - 2 * DAY).toISOString(),
    registrationClosesAt: new Date(now + 10 * DAY).toISOString(),
    capacity: 2,
    registeredCount: 2 // already at capacity — used to demo the capacity rule
  },
  {
    id: 'e3',
    name: 'Partner Networking Night',
    status: 'planning', // not yet confirmed — used to demo the status rule
    registrationEnabled: false,
    registrationOpensAt: new Date(now + 4 * DAY).toISOString(),
    registrationClosesAt: new Date(now + 14 * DAY).toISOString(),
    capacity: 100,
    registeredCount: 0
  },
  {
    id: 'e4',
    name: 'Q1 Client Briefing',
    status: 'confirmed',
    registrationEnabled: true,
    registrationOpensAt: new Date(now + 2 * DAY).toISOString(), // opens in the future — used to demo the period rule
    registrationClosesAt: new Date(now + 20 * DAY).toISOString(),
    capacity: 50,
    registeredCount: 0
  }
]

export function registrationEligibility(event) {
  const nowTs = Date.now()
  if (event.status !== 'confirmed') {
    return { eligible: false, reason: 'This event has not been confirmed yet.' }
  }
  if (!event.registrationEnabled) {
    return { eligible: false, reason: 'Registration has not been enabled for this event.' }
  }
  if (nowTs < new Date(event.registrationOpensAt).getTime()) {
    return { eligible: false, reason: `Registration opens ${new Date(event.registrationOpensAt).toLocaleDateString()}.` }
  }
  if (nowTs > new Date(event.registrationClosesAt).getTime()) {
    return { eligible: false, reason: 'Registration has closed for this event.' }
  }
  if (event.registeredCount >= event.capacity) {
    return { eligible: false, reason: 'This event has reached capacity.' }
  }
  return { eligible: true, reason: null }
}
