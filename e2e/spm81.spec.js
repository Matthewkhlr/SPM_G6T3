import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { completeRequestPayload } from './support/api-data.js'
import { eventApi, submitEvent } from './support/event.js'

function windowAround(daysFromNow, hoursOpen = 5) {
  const opens = new Date(Date.now() + daysFromNow * 24 * 60 * 60 * 1000)
  const closes = new Date(opens.getTime() + hoursOpen * 60 * 60 * 1000)
  return { opens, closes }
}

test.describe('SPM-81 State registration needs at submission time', () => {
  test('TC-SPM81-AC01 the request carries a required registration-needed indicator', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.locator('.nav-item').getByText('New Request', { exact: true }).click()
    await expect(page.getByTestId('registration-needed')).toBeVisible()
    const missing = await eventApi('POST', '', 'EO-01', {
      eventName: 'AUTO-SPM81-flag',
      purpose: 'x',
      category: 'meeting',
      proposedStartAt: new Date(Date.now() + 10 * 86400000).toISOString(),
      proposedEndAt: new Date(Date.now() + 10 * 86400000 + 3600000).toISOString(),
      expectedAttendance: 10,
    })
    expect([400, 422]).toContain(missing.status)
    expect(JSON.stringify(missing.body)).toMatch(/registration/i)
  })

  test('TC-SPM81-AC02 when registration is needed the organiser may set open, close, and capacity', async () => {
    const { opens, closes } = windowAround(3, 24)
    const start = new Date(Date.now() + 10 * 86400000)
    const created = await eventApi(
      'POST',
      '',
      'EO-01',
      completeRequestPayload('AUTO-SPM81-window', {
        registrationEnabled: true,
        registrationOpensAt: opens.toISOString(),
        registrationClosesAt: closes.toISOString(),
        capacity: 40,
        expectedAttendance: 40,
        proposedStartAt: start.toISOString(),
        proposedEndAt: new Date(start.getTime() + 2 * 3600000).toISOString(),
      }),
    )
    expect(created.status).toBe(201)
    expect(created.body.registrationEnabled).toBe(true)
    expect(created.body.registrationOpensAt).toBeTruthy()
    expect(created.body.registrationClosesAt).toBeTruthy()
    expect(created.body.capacity).toBe(40)
  })

  test('TC-SPM81-AC03 registration needed with blank period or capacity still submits and flags outstanding details', async () => {
    const created = await eventApi(
      'POST',
      '',
      'EO-01',
      completeRequestPayload('AUTO-SPM81-outstanding', {
        registrationEnabled: true,
        registrationOpensAt: null,
        registrationClosesAt: null,
        capacity: 0,
      }),
    )
    const submitted = await submitEvent(created.body.eventId)
    expect(submitted.status).toBe(200)
    expect(submitted.body.registrationDetailsOutstanding || submitted.body.registrationOutstanding).toBe(
      true,
    )
  })

  test('TC-SPM81-AC04 a closing time that is not after the opening time is rejected', async () => {
    const opens = new Date(Date.now() + 3 * 86400000)
    const denied = await eventApi(
      'POST',
      '',
      'EO-01',
      completeRequestPayload('AUTO-SPM81-close', {
        registrationEnabled: true,
        registrationOpensAt: opens.toISOString(),
        registrationClosesAt: opens.toISOString(),
      }),
    )
    expect([400, 422]).toContain(denied.status)
    expect(JSON.stringify(denied.body)).toMatch(/after|closing|opening/i)
  })

  test('TC-SPM81-AC05 a closing time later than the event start is rejected', async () => {
    const start = new Date(Date.now() + 10 * 86400000)
    const denied = await eventApi(
      'POST',
      '',
      'EO-01',
      completeRequestPayload('AUTO-SPM81-late-close', {
        registrationEnabled: true,
        proposedStartAt: start.toISOString(),
        proposedEndAt: new Date(start.getTime() + 2 * 3600000).toISOString(),
        registrationOpensAt: new Date(start.getTime() - 5 * 86400000).toISOString(),
        registrationClosesAt: new Date(start.getTime() + 3600000).toISOString(),
      }),
    )
    expect([400, 422]).toContain(denied.status)
    expect(JSON.stringify(denied.body)).toMatch(/start|before|closing/i)
  })

  test('TC-SPM81-AC06 capacity above expected attendance warns but may proceed', async ({ page }) => {
    const start = new Date(Date.now() + 12 * 86400000)
    await login(page, account('EO-01'))
    await page.locator('.nav-item').getByText('New Request', { exact: true }).click()
    await page.getByTestId('event-name-input').fill('AUTO-SPM81-cap')
    await page.getByTestId('expected-attendance').fill('20')
    await page.getByTestId('registration-needed').check()
    await page.getByTestId('registration-capacity').fill('80')
    await page.getByTestId('event-save-draft').click()
    await expect(page.getByTestId('capacity-above-attendance-warning')).toBeVisible()
    await page.getByTestId('capacity-proceed').click()
    const created = await eventApi(
      'POST',
      '',
      'EO-01',
      completeRequestPayload('AUTO-SPM81-cap-api', {
        registrationEnabled: true,
        expectedAttendance: 20,
        capacity: 80,
        proposedStartAt: start.toISOString(),
        proposedEndAt: new Date(start.getTime() + 2 * 3600000).toISOString(),
      }),
    )
    expect([201, 200]).toContain(created.status)
  })

  test('TC-SPM81-AC07 when registration is not needed, no registration screen or action appears', async ({
    page,
  }) => {
    const created = await eventApi(
      'POST',
      '',
      'EO-01',
      completeRequestPayload('AUTO-SPM81-off', { registrationEnabled: false }),
    )
    await submitEvent(created.body.eventId)
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${created.body.eventId}`)
    await expect(page.getByTestId('registration-admin')).toHaveCount(0)
    await expect(page.getByRole('link', { name: /register/i })).toHaveCount(0)
    const attendee = await eventApi('GET', `/${created.body.eventId}/registrations`, 'ATT-01')
    expect([403, 404]).toContain(attendee.status)
  })
})
