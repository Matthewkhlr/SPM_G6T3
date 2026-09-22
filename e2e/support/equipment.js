import { expect } from '@playwright/test'
import { account } from './test-data.js'
import { firebaseIdToken, bearer } from './auth.js'
import {
  equipmentPeriod,
  equipmentRequestPayload,
  newEquipmentPayload,
  serviceUrls,
} from './api-data.js'
import { assignCoordinator, createSubmittedEvent } from './event.js'

const tokens = {}

export async function equipmentToken(id) {
  if (!tokens[id]) tokens[id] = await firebaseIdToken(null, account(id))
  return tokens[id]
}

export async function equipmentApi(method, path, accountId, body) {
  const response = await fetch(`${serviceUrls.equipment}${path}`, {
    method,
    headers: {
      ...bearer(await equipmentToken(accountId)),
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

export async function createEquipment(label, extras = {}) {
  const created = await equipmentApi('POST', '/equipment', 'TS-01', {
    ...newEquipmentPayload(label),
    ...extras,
  })
  expect(created.status, JSON.stringify(created.body)).toBe(201)
  return created.body
}

export async function createPendingRequest(extras = {}) {
  const sequence = extras.sequence ?? 310
  const payload = {
    ...equipmentRequestPayload(sequence, extras.eventId || 'e3'),
    ...extras,
  }
  delete payload.sequence
  const created = await equipmentApi('POST', '/equipment/requests', 'EC-01', payload)
  expect(created.status, JSON.stringify(created.body)).toBe(201)
  return created.body
}

export async function approveRequest(requestId, note = 'AUTO-approve') {
  const reviewed = await equipmentApi('POST', `/equipment/requests/${requestId}/review`, 'TS-01', {
    approve: true,
    reviewNote: note,
  })
  expect(reviewed.status, JSON.stringify(reviewed.body)).toBe(200)
  return reviewed.body
}

export async function checkAvailability(eventId) {
  return equipmentApi('POST', '/equipment/availability', 'TS-01', { eventId })
}

export async function reserveQuantity(eventId, equipmentId, quantity, window) {
  return equipmentApi('POST', '/equipment/reservations', 'TS-01', {
    eventId,
    equipmentId,
    quantity,
    startsAt: window.startsAt,
    endsAt: window.endsAt,
  })
}

export async function planningEventWithRequest(name, extras = {}) {
  const event = await createSubmittedEvent('EO-01', name)
  await assignCoordinator(event.eventId, 'u2', 'EC-01')
  const window = extras.window || equipmentPeriod(extras.sequence ?? 320)
  const request = await createPendingRequest({
    eventId: event.eventId,
    equipmentId: extras.equipmentId || 'eq1',
    quantity: extras.quantity ?? 1,
    startsAt: window.startsAt,
    endsAt: window.endsAt,
    technicalRequirements: extras.technicalRequirements || 'AUTO-EQ-REQ',
  })
  return { event, request, window }
}
