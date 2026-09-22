import { test, expect } from '@playwright/test'
import { account } from './support/test-data.js'
import { authedApi } from './support/auth.js'
import { serviceUrls } from './support/api-data.js'

const ORG1_EVENTS = ['e1', 'e2', 'e3', 'e4']
const FOREIGN_EVENT = 'e5'
const FOREIGN_NAME = 'Beacon Q4 Showcase'
const STAFF_FIELDS = [
  'purpose',
  'venueRequirements',
  'accessibilityNeeds',
  'equipmentRequirements',
  'layoutPreference',
  'coordinatorId',
  'coordinatorName',
  'organiserId',
  'organisationId',
]

function eventIds(body) {
  return (Array.isArray(body) ? body : []).map((event) => event.eventId)
}

function expectHiddenEvent(result, eventId, leakedName) {
  expect([403, 404], JSON.stringify(result.body)).toContain(result.status)
  const payload = JSON.stringify(result.body ?? {})
  expect(payload).not.toContain(leakedName)
  expect(result.body?.eventId).not.toBe(eventId)
  expect(result.body?.eventName).toBeFalsy()
}

test.describe('SPM-47 Multi-Tenant Event Access Restriction — API', () => {
  test('TC-SPM47-AC01 organiser list is limited to their organisation', async () => {
    const own = await authedApi('GET', `${serviceUrls.event}/events`, 'EO-01')
    expect(own.status, JSON.stringify(own.body)).toBe(200)
    const ownIds = eventIds(own.body)
    for (const eventId of ORG1_EVENTS) {
      expect(ownIds, `EO-01 missing ${eventId}`).toContain(eventId)
    }
    expect(ownIds).not.toContain(FOREIGN_EVENT)
    expect(JSON.stringify(own.body)).not.toContain(FOREIGN_NAME)

    const other = await authedApi('GET', `${serviceUrls.event}/events`, 'EO-02')
    expect(other.status, JSON.stringify(other.body)).toBe(200)
    const otherIds = eventIds(other.body)
    expect(otherIds).toContain(FOREIGN_EVENT)
    for (const eventId of ORG1_EVENTS) {
      expect(otherIds, `EO-02 leaked ${eventId}`).not.toContain(eventId)
    }
  })

  test('TC-SPM47-AC02 cross-organisation event GET is 403 or 404', async () => {
    const denied = await authedApi('GET', `${serviceUrls.event}/events/${FOREIGN_EVENT}`, 'EO-01')
    expectHiddenEvent(denied, FOREIGN_EVENT, FOREIGN_NAME)

    const allowedForeign = await authedApi(
      'GET',
      `${serviceUrls.event}/events/${FOREIGN_EVENT}`,
      'EO-02',
    )
    expect(allowedForeign.status, JSON.stringify(allowedForeign.body)).toBe(200)
    expect(allowedForeign.body.eventId).toBe(FOREIGN_EVENT)

    const allowedOwn = await authedApi('GET', `${serviceUrls.event}/events/e1`, 'EO-01')
    expect(allowedOwn.status, JSON.stringify(allowedOwn.body)).toBe(200)
    expect(allowedOwn.body.eventId).toBe('e1')
  })

  test('TC-SPM47-AC03 attendee sees public events and only their registrations', async () => {
    const list = await authedApi('GET', `${serviceUrls.event}/events`, 'ATT-01')
    expect(list.status, JSON.stringify(list.body)).toBe(200)
    expect(eventIds(list.body)).not.toContain('e3')

    const draft = await authedApi('GET', `${serviceUrls.event}/events/e3`, 'ATT-01')
    expectHiddenEvent(draft, 'e3', 'Partner Networking Night')

    const publicEvent = await authedApi('GET', `${serviceUrls.event}/events/e1`, 'ATT-01')
    expect(publicEvent.status, JSON.stringify(publicEvent.body)).toBe(200)
    expect(publicEvent.body.eventId).toBe('e1')
    expect(publicEvent.body.eventName).toBeTruthy()
    expect(publicEvent.body.status).toBeTruthy()
    for (const field of STAFF_FIELDS) {
      expect(publicEvent.body, field).not.toHaveProperty(field)
    }

    const attendee = account('ATT-01')
    const registered = await authedApi('POST', `${serviceUrls.registration}/registrations`, 'ATT-01', {
      eventId: 'e1',
      name: attendee.displayName,
      email: attendee.email,
    })
    expect([201, 409], JSON.stringify(registered.body)).toContain(registered.status)

    const registrations = await authedApi(
      'GET',
      `${serviceUrls.registration}/registrations?eventId=e1`,
      'ATT-01',
    )
    expect(registrations.status, JSON.stringify(registrations.body)).toBe(200)
    expect(Array.isArray(registrations.body)).toBe(true)
    expect(registrations.body.some((row) => row.attendeeEmail === attendee.email)).toBe(true)
    expect(registrations.body.some((row) => row.attendeeRegistrationId === 'r1')).toBe(false)
    expect(registrations.body.some((row) => row.attendeeEmail === 'one@example.com')).toBe(false)

    const foreignRegistration = await authedApi(
      'GET',
      `${serviceUrls.registration}/registrations/r1`,
      'ATT-01',
    )
    expect([403, 404], JSON.stringify(foreignRegistration.body)).toContain(foreignRegistration.status)
  })
})
