const DAY = 24 * 60 * 60 * 1000

function period(daysFromNow) {
  const start = new Date(Date.now() + daysFromNow * DAY)
  start.setUTCHours(10, 0, 0, 0)
  const end = new Date(start.getTime() + 2 * 60 * 60 * 1000)
  return { start, end }
}

export function venueBookingPayload(sequence = 30) {
  const { start, end } = period(sequence)
  return {
    venueId: 'v1',
    eventId: 'e1',
    startsAt: start.toISOString(),
    endsAt: end.toISOString(),
    setupStartsAt: new Date(start.getTime() - 60 * 60 * 1000).toISOString(),
    teardownEndsAt: new Date(end.getTime() + 60 * 60 * 1000).toISOString(),
    requirementsSnapshot: `AUTO-SPM45-${Date.now()}-${sequence}`,
  }
}

export function equipmentRequestPayload(sequence = 45) {
  const { start, end } = period(sequence)
  return {
    eventId: 'e1',
    equipmentId: 'eq1',
    quantity: 1,
    technicalRequirements: `AUTO-SPM45-HDMI-${Date.now()}-${sequence}`,
    startsAt: start.toISOString(),
    endsAt: end.toISOString(),
  }
}

export const serviceUrls = {
  user: process.env.VITE_USER_SERVICE_URL || 'http://127.0.0.1:8001',
  event: process.env.VITE_EVENT_SERVICE_URL || 'http://127.0.0.1:8002',
  venue: process.env.VITE_VENUE_SERVICE_URL || 'http://127.0.0.1:8003',
  equipment: process.env.VITE_EQUIPMENT_SERVICE_URL || 'http://127.0.0.1:8004',
}
