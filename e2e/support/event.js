import { expect } from '@playwright/test'
import { authedApi } from './auth.js'
import { newEventPayload, serviceUrls } from './api-data.js'

export function eventUrl(path = '') {
  return `${serviceUrls.event}/events${path}`
}

export async function eventApi(method, path, accountId, body) {
  return authedApi(method, eventUrl(path), accountId, body)
}

export async function createDraftEvent(accountId = 'EO-01', name) {
  const created = await eventApi('POST', '', accountId, newEventPayload(name))
  expect(created.status, JSON.stringify(created.body)).toBe(201)
  expect(created.body.status).toMatch(/draft|created/i)
  return created.body
}

export async function createSubmittedEvent(accountId = 'EO-01', name) {
  const created = await createDraftEvent(accountId, name)
  const submitted = await eventApi('POST', `/${created.eventId}/submit`, accountId)
  expect(submitted.status, JSON.stringify(submitted.body)).toBe(200)
  expect(submitted.body.status).toMatch(/submitted/i)
  return submitted.body
}

export async function createNameOnlyDraft(accountId = 'EO-01', name) {
  const created = await eventApi('POST', '', accountId, { eventName: name })
  expect(created.status, JSON.stringify(created.body)).toBe(201)
  expect(created.body.status).toMatch(/draft|created/i)
  return created.body
}

export async function submitEvent(eventId, accountId = 'EO-01') {
  return eventApi('POST', `/${eventId}/submit`, accountId)
}

export async function raiseChangeRequest(eventId, accountId, body) {
  return eventApi('POST', `/${eventId}/change-requests`, accountId, body)
}

export async function assignCoordinator(eventId, coordinatorId, assignedBy = 'EC-01') {
  const result = await eventApi(
    'POST',
    `/${eventId}/assign-coordinator`,
    assignedBy,
    { coordinatorId },
  )
  expect(result.status, JSON.stringify(result.body)).toBe(201)
  return result.body
}
