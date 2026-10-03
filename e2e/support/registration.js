import { account } from './test-data.js'
import { firebaseIdToken, bearer } from './auth.js'
import { serviceUrls } from './api-data.js'

const tokens = {}

async function token(id) {
  if (!tokens[id]) tokens[id] = await firebaseIdToken(null, account(id))
  return tokens[id]
}

export async function registrationApi(method, path, accountId, body) {
  const response = await fetch(`${serviceUrls.registration}${path}`, {
    method,
    headers: {
      ...bearer(await token(accountId)),
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

export async function notificationApi(method, path, accountId, body) {
  const response = await fetch(`${serviceUrls.notification}${path}`, {
    method,
    headers: {
      ...bearer(await token(accountId)),
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

export function guestRegistration(eventId, label = 'AUTO') {
  const stamp = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
  return {
    eventId,
    name: `${label} Guest`,
    email: `${label.toLowerCase()}-${stamp}@example.com`,
  }
}
