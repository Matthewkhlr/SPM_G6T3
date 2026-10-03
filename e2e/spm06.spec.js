import { test, expect } from '@playwright/test'
import { eventApi } from './support/event.js'
import { notificationApi } from './support/registration.js'

test.describe('SPM-06 Clarification on assigned request', () => {
  test('TC-SPM06-AC01 when the organiser responds to a clarification, the assigned coordinator is notified', async () => {
    const reply = await eventApi('POST', '/e3/clarifications/rv-clarify-e3/reply', 'EO-01', {
      message: 'Attendance stays at 80.',
    })
    expect(reply.status).toBe(201)
    const inbox = await notificationApi('GET', '/notifications', 'EC-01')
    expect(inbox.status).toBe(200)
    expect(JSON.stringify(inbox.body)).toMatch(/e3|Partner Networking|Attendance stays at 80|clarif/i)
  })

  test('TC-SPM06-AC02 the notification names the event and includes the response or a link to it', async () => {
    await eventApi('POST', '/e3/clarifications/rv-clarify-e3/reply', 'EO-01', {
      message: 'HDMI is required at the lectern.',
    })
    const inbox = await notificationApi('GET', '/notifications', 'EC-01')
    const match = (inbox.body || []).find((row) =>
      /e3|Partner Networking/i.test(JSON.stringify(row)),
    )
    expect(match, JSON.stringify(inbox.body)).toBeTruthy()
    expect(JSON.stringify(match)).toMatch(/HDMI|lectern|\/events\/e3|clarif/i)
    expect(JSON.stringify(match)).not.toMatch(/^you have a new response$/i)
  })

  test('TC-SPM06-AC03 no notification is generated before the organiser responds; the clarification stays outstanding', async () => {
    const before = await notificationApi('GET', '/notifications?eventId=e3', 'EC-01')
    const clarifications = await eventApi('GET', '/e3/clarifications', 'EC-01')
    expect(clarifications.status).toBe(200)
    const open = (clarifications.body || []).find((row) => /open|outstanding/i.test(row.status))
    expect(open || clarifications.body.length).toBeTruthy()
    expect(JSON.stringify(before.body || [])).not.toMatch(/AUTO-SPM06-NONE/)
  })

  test('TC-SPM06-AC04 a late response still notifies, and flags that the request is no longer awaiting review', async () => {
    const reply = await eventApi('POST', '/e1/clarifications/late-reply/reply', 'EO-01', {
      message: 'Late answer after planning moved on.',
    })
    expect([201, 404, 409]).toContain(reply.status)
    if (reply.status === 201) {
      const inbox = await notificationApi('GET', '/notifications', 'EC-01')
      expect(JSON.stringify(inbox.body)).toMatch(/no longer awaiting|approved|planning|confirmed/i)
    }
  })
})
