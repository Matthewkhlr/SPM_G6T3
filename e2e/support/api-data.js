const DAY = 24 * 60 * 60 * 1000

function period(daysFromNow) {
  const start = new Date(Date.now() + daysFromNow * DAY)
  start.setUTCHours(10, 0, 0, 0)
  const end = new Date(start.getTime() + 2 * 60 * 60 * 1000)
  return { start, end }
}

export function equipmentRequestPayload(sequence = 45, eventId = 'e1') {
  const { start, end } = period(sequence)
  return {
    eventId,
    equipmentId: 'eq1',
    quantity: 1,
    technicalRequirements: `AUTO-SPM45-HDMI-${Date.now()}-${sequence}`,
    startsAt: start.toISOString(),
    endsAt: end.toISOString(),
  }
}

export function venuePeriod(daysFromNow, hours = 2) {
  const start = new Date(Date.now() + daysFromNow * DAY)
  start.setUTCHours(10, 0, 0, 0)
  const end = new Date(start.getTime() + hours * 60 * 60 * 1000)
  return {
    startsAt: start.toISOString(),
    endsAt: end.toISOString(),
    setupStartsAt: new Date(start.getTime() - 60 * 60 * 1000).toISOString(),
    teardownEndsAt: new Date(end.getTime() + 60 * 60 * 1000).toISOString(),
  }
}

export function venueBookingPayload(sequence = 30, eventId = 'e1', venueId = 'v1') {
  return {
    venueId,
    eventId,
    ...venuePeriod(sequence),
    requirementsSnapshot: `AUTO-${Date.now()}-${sequence}`,
  }
}

export function venueUnavailabilityPayload(sequence = 80, reason = 'maintenance') {
  const window = venuePeriod(sequence, 4)
  return {
    startsAt: window.startsAt,
    endsAt: window.endsAt,
    reason,
    note: `AUTO-UNAVAIL-${Date.now()}-${sequence}`,
  }
}

export function newVenuePayload(label = `AUTO-VENUE-${Date.now()}`) {
  return {
    code: `AUTO-${Date.now().toString().slice(-6)}`,
    name: label,
    location: 'HarbourFront Centre',
    address: '1 HarbourFront Walk, Singapore 098585',
    floor: '9',
    description: 'Created by acceptance tests.',
    facilities: ['Projector'],
    accessibility: ['Wheelchair accessible'],
    layouts: [
      { name: 'Boardroom', capacity: 12 },
      { name: 'Classroom', capacity: 20 },
    ],
    operatingHours: [{ day: 'Mon', opens: '08:00', closes: '18:00' }],
    turnaroundMinutes: 15,
  }
}

export function equipmentPeriod(daysFromNow, hours = 2) {
  return venuePeriod(daysFromNow, hours)
}

export function newEquipmentPayload(label = `AUTO-EQ-${Date.now()}`) {
  return {
    code: `AUTO-${Date.now().toString().slice(-6)}`,
    name: label,
    category: 'display',
    description: 'Created by the equipment suite.',
    totalQuantity: 5,
    homeLocation: 'Marina Hall store',
    technicalNotes: 'HDMI adapters included.',
  }
}

export function newEventPayload(name = `AUTO-EVENT-${Date.now()}`) {
  const start = new Date(Date.now() + 40 * DAY)
  start.setUTCHours(10, 0, 0, 0)
  const end = new Date(start.getTime() + 2 * 60 * 60 * 1000)
  return {
    eventName: name,
    purpose: 'Acceptance test event.',
    description: 'Created by the planning-review suite.',
    category: 'meeting',
    proposedStartAt: start.toISOString(),
    proposedEndAt: end.toISOString(),
    expectedAttendance: 24,
    venueRequirements: 'Boardroom.',
    accessibilityNeeds: 'Wheelchair access required.',
    equipmentRequirements: 'Projector.',
    layoutPreference: 'Boardroom',
    registrationEnabled: false,
    capacity: 30,
  }
}

export const EVENT_PROPOSED_DATE_NEAR_DAYS = 14

export const serviceUrls = {
  user: process.env.VITE_USER_SERVICE_URL || 'http://127.0.0.1:8001',
  event: process.env.VITE_EVENT_SERVICE_URL || 'http://127.0.0.1:8002',
  venue: process.env.VITE_VENUE_SERVICE_URL || 'http://127.0.0.1:8003',
  equipment: process.env.VITE_EQUIPMENT_SERVICE_URL || 'http://127.0.0.1:8004',
  registration: process.env.VITE_REGISTRATION_SERVICE_URL || 'http://127.0.0.1:8005',
  notification: process.env.VITE_NOTIFICATION_SERVICE_URL || 'http://127.0.0.1:8006',
}
