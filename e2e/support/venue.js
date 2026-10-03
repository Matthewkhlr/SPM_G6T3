import { expect } from '@playwright/test'
import { account } from './test-data.js'
import { firebaseIdToken, bearer } from './auth.js'
import { serviceUrls, venueBookingPayload } from './api-data.js'

const tokens = {}

export async function venueToken(id) {
  if (!tokens[id]) tokens[id] = await firebaseIdToken(null, account(id))
  return tokens[id]
}

export async function venueRequest(method, path, accountId, body) {
  const response = await fetch(`${serviceUrls.venue}${path}`, {
    method,
    headers: {
      ...bearer(await venueToken(accountId)),
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

export async function notificationRequest(path, accountId) {
  const response = await fetch(`${serviceUrls.notification}${path}`, {
    method: 'GET',
    headers: {
      ...bearer(await venueToken(accountId)),
      'Content-Type': 'application/json',
    },
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

export async function createPendingBooking(accountId, sequence, extras = {}) {
  const result = await venueRequest(
    'POST',
    '/venues/bookings',
    accountId,
    { ...venueBookingPayload(sequence, extras.eventId || 'e1', extras.venueId || 'v1'), ...extras },
  )
  expect(result.status, JSON.stringify(result.body)).toBe(201)
  return result.body
}
