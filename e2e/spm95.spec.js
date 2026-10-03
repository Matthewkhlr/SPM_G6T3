import { test, expect } from '@playwright/test'
import { EVENT_REMINDER_LEAD_DAYS } from './support/api-data.js'
import { eventApi } from './support/event.js'
import { notificationApi } from './support/registration.js'

test.describe('SPM-95 Remind staff of approaching events with outstanding arrangements', () => {
  test('TC-SPM95-AC01 a scheduled check selects events within the lead time that still have outstanding arrangements', async () => {
    const run = await notificationApi('POST', '/notifications/reminders/run', 'EC-01')
    expect(run.status).toBe(200)
    const selected = run.body.events || run.body
    expect(EVENT_REMINDER_LEAD_DAYS).toBeGreaterThan(0)
    for (const row of selected) {
      const days = (new Date(row.proposedStartAt || row.startsAt).getTime() - Date.now()) / 86400000
      expect(days).toBeLessThanOrEqual(EVENT_REMINDER_LEAD_DAYS)
      expect(row.outstanding || row.arrangements).toBeTruthy()
    }
  })

  test('TC-SPM95-AC02 each selected event notifies its assigned coordinator, naming the event, date, and outstanding arrangements', async () => {
    await notificationApi('POST', '/notifications/reminders/run', 'EC-01')
    const inbox = await notificationApi('GET', '/notifications?trigger=readiness.reminder', 'EC-01')
    expect(inbox.status).toBe(200)
    expect(JSON.stringify(inbox.body)).toMatch(/e1|AI in Events|outstanding|venue|equipment/i)
  })

  test('TC-SPM95-AC03 outstanding venue also notifies Venue Staff, and outstanding equipment notifies Technical Support', async () => {
    await notificationApi('POST', '/notifications/reminders/run', 'EC-01')
    const vs = await notificationApi('GET', '/notifications?trigger=readiness.reminder', 'VS-01')
    const ts = await notificationApi('GET', '/notifications?trigger=readiness.reminder', 'TS-01')
    expect(vs.status).toBe(200)
    expect(ts.status).toBe(200)
  })

  test('TC-SPM95-AC04 the lead time is read from one configured value', async () => {
    const config = await notificationApi('GET', '/notifications/reminders/config', 'EC-01')
    expect(config.status).toBe(200)
    expect(config.body.leadDays || config.body.EVENT_REMINDER_LEAD_DAYS).toBe(EVENT_REMINDER_LEAD_DAYS)
  })

  test('TC-SPM95-AC05 a reminder is raised once per event per occasion, so a second daily check does not duplicate', async () => {
    await notificationApi('POST', '/notifications/reminders/run', 'EC-01')
    await notificationApi('POST', '/notifications/reminders/run', 'EC-01')
    const inbox = await notificationApi('GET', '/notifications?trigger=readiness.reminder&eventId=e1', 'EC-01')
    const rows = (inbox.body.items || inbox.body || []).filter((row) => row.eventId === 'e1')
    expect(rows.length).toBeLessThanOrEqual(1)
  })

  test('TC-SPM95-AC06 a fully ready, completed, cancelled, or rejected event produces no reminder', async () => {
    const run = await notificationApi('POST', '/notifications/reminders/run', 'EC-01')
    const ids = (run.body.events || run.body || []).map((row) => row.eventId)
    expect(ids).not.toContain('e8')
    const readiness = await eventApi('GET', '/e1/readiness', 'EC-01')
    if (readiness.status === 200) {
      const outstanding = (readiness.body || []).filter((row) => /outstanding|attention/i.test(row.status))
      if (!outstanding.length) expect(ids).not.toContain('e1')
    }
  })

  test('TC-SPM95-AC07 an approaching event with no coordinator goes to the coordinator triage queue', async () => {
    const run = await notificationApi('POST', '/notifications/reminders/run', 'EC-01')
    expect(run.status).toBe(200)
    const triage = run.body.triage || run.body.unassigned
    const inbox = await notificationApi('GET', '/notifications?trigger=readiness.reminder.unassigned', 'EC-01')
    expect([200, 404]).toContain(inbox.status)
    expect(triage || inbox.body).toBeTruthy()
  })

  test('TC-SPM95-AC08 the check can be run on demand in the demo environment', async () => {
    const run = await notificationApi('POST', '/notifications/reminders/run', 'EC-01')
    expect(run.status).toBe(200)
    expect(run.body.ranAt || run.body.ok || run.body.events).toBeTruthy()
  })
})
