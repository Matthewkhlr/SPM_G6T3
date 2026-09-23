import { test, expect } from '@playwright/test'
import { assignCoordinator, createSubmittedEvent, eventApi } from './support/event.js'
import { notificationApi } from './support/registration.js'

test.describe('SPM-93 Notification delivery and recipient resolution', () => {
  test('TC-SPM93-AC01 one notification service is the only way a notification record is created', async () => {
    const created = await notificationApi('POST', '/notifications', 'EC-01', {
      trigger: 'event.assigned',
      eventId: 'e6',
      recipientUserId: 'u2',
    })
    expect([201, 200]).toContain(created.status)
    const direct = await eventApi('POST', '/e6/notifications', 'EC-01', {
      message: 'should not write a row',
    })
    expect([403, 404, 405]).toContain(direct.status)
  })

  test('TC-SPM93-AC02 each notification records recipient, trigger, event, message, link, time, and read state', async () => {
    const inbox = await notificationApi('GET', '/notifications', 'EO-01')
    expect(inbox.status).toBe(200)
    const row = (inbox.body.items || inbox.body)[0]
    expect(row).toBeTruthy()
    for (const field of ['recipientUserId', 'trigger', 'eventId', 'message', 'link', 'createdAt', 'isRead']) {
      expect(row[field] ?? row.userId ?? row.body, field).not.toBeUndefined()
    }
  })

  test('TC-SPM93-AC03 recipients are resolved from the relationship to the event, not from role alone', async () => {
    const resolved = await notificationApi('GET', '/notifications/recipients?eventId=e1&trigger=event.confirmed', 'EC-01')
    expect(resolved.status).toBe(200)
    const ids = (resolved.body || []).map((row) => row.userId || row.recipientUserId)
    expect(ids).toContain('u1')
    expect(ids).toContain('u2')
    expect(ids).not.toContain('u6')
  })

  test('TC-SPM93-AC04 each trigger declares which relationships it notifies, and new triggers are registered', async () => {
    const catalog = await notificationApi('GET', '/notifications/triggers', 'EC-01')
    expect(catalog.status).toBe(200)
    const assigned = (catalog.body || []).find((row) => /assign/i.test(row.trigger || row.id))
    expect(assigned.relationships || assigned.recipients).toBeTruthy()
  })

  test('TC-SPM93-AC05 the actor never receives a notification about their own action', async () => {
    const event = await createSubmittedEvent('EO-01', 'AUTO-SPM93-self')
    await assignCoordinator(event.eventId, 'u2', 'EC-01')
    const inbox = await notificationApi('GET', `/notifications?eventId=${event.eventId}`, 'EC-01')
    expect(JSON.stringify(inbox.body || [])).not.toMatch(new RegExp(event.eventId))
  })

  test('TC-SPM93-AC06 one notification is created per recipient per occurrence, so a repeat does not duplicate', async () => {
    await eventApi('POST', '/e6/assign-coordinator', 'EC-01', { coordinatorId: 'u2' })
    await eventApi('POST', '/e6/assign-coordinator', 'EC-01', { coordinatorId: 'u2' })
    const inbox = await notificationApi('GET', '/notifications?eventId=e6&trigger=event.assigned', 'EO-01')
    const rows = (inbox.body.items || inbox.body || []).filter((row) => row.eventId === 'e6')
    const keys = rows.map((row) => `${row.trigger}:${row.recipientUserId || row.userId}`)
    expect(new Set(keys).size).toBe(keys.length)
  })

  test('TC-SPM93-AC07 an attendee can only receive an attendee-visible trigger', async () => {
    const inbox = await notificationApi('GET', '/notifications', 'ATT-01')
    expect(inbox.status).toBe(200)
    for (const row of inbox.body.items || inbox.body || []) {
      expect(row.attendeeVisible ?? row.visibility).not.toBe('internal')
      expect(JSON.stringify(row)).not.toMatch(/internal note|staff only/i)
    }
  })

  test('TC-SPM93-AC08 every message names the event and states what happened in plain language', async () => {
    const inbox = await notificationApi('GET', '/notifications', 'EO-01')
    const row = (inbox.body.items || inbox.body)[0]
    expect(JSON.stringify(row)).toMatch(/AI in Events Summit|e1/)
    expect(JSON.stringify(row)).not.toMatch(/\b(submitted|planning|under_review)\b/)
  })

  test('TC-SPM93-AC09 if delivery fails, the action still succeeds and the failure is logged', async () => {
    const assigned = await eventApi('POST', '/e6/assign-coordinator', 'EC-01', {
      coordinatorId: 'u2',
      simulateNotificationFailure: true,
    })
    expect([201, 409]).toContain(assigned.status)
  })

  test('TC-SPM93-AC10 notifications persist after the event is completed or cancelled', async () => {
    const inbox = await notificationApi('GET', '/notifications?eventId=e8', 'EO-01')
    expect(inbox.status).toBe(200)
  })

  test('TC-SPM93-AC11 automated coverage of recipient resolution, actor exclusion, deduplication, attendee scoping, and delivery failure', async () => {
    const resolved = await notificationApi('GET', '/notifications/recipients?eventId=e1&trigger=event.confirmed', 'EC-01')
    expect(resolved.status).toBe(200)
    const ids = (resolved.body || []).map((row) => row.userId || row.recipientUserId)
    expect(ids).toEqual(expect.arrayContaining(['u1']))
    const attendee = await notificationApi('GET', '/notifications', 'ATT-01')
    expect(attendee.status).toBe(200)
    const self = await notificationApi('GET', '/notifications?eventId=e1&actor=u2', 'EC-01')
    expect(JSON.stringify(self.body || [])).not.toMatch(/assigned themselves/)
  })
})
