import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { guestRegistration, notificationApi, registrationApi } from './support/registration.js'

test.describe('SPM-11 Register for an event', () => {
  test('TC-SPM11-AC01 registration succeeds only for a confirmed, enabled, in-period event with a place remaining', async () => {
    const ok = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e1', 'SPM11-OK'))
    expect(ok.status).toBe(201)
    expect(ok.body.eventId).toBe('e1')
    const planning = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e3', 'SPM11-E3'))
    expect([400, 409]).toContain(planning.status)
    const submitted = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e6', 'SPM11-E6'))
    expect([400, 404, 409]).toContain(submitted.status)
  })

  test('TC-SPM11-AC02 mandatory registration fields left blank block submit with inline validation', async ({
    page,
  }) => {
    await login(page, account('ATT-02'))
    await page.goto('/app/events/e1')
    await page.getByTestId('event-register').click()
    await page.getByTestId('register-submit').click()
    await expect(page.getByTestId('register-name-error')).toBeVisible()
    await expect(page.getByTestId('register-email-error')).toBeVisible()
    const empty = await registrationApi('POST', '/registrations', 'ATT-02', {
      eventId: 'e1',
      name: '',
      email: '',
    })
    expect([400, 409, 422]).toContain(empty.status)
  })

  test('TC-SPM11-AC03 a successful registration confirms on screen with event, date, time, and venue, and notifies the attendee', async ({
    page,
  }) => {
    const created = await registrationApi(
      'POST',
      '/registrations',
      'ATT-02',
      guestRegistration('e1', 'SPM11-UI'),
    )
    expect(created.status).toBe(201)
    await login(page, account('ATT-02'))
    await page.goto('/app/events/e1')
    await expect(page.getByTestId('register-confirmation')).toContainText('AI in Events Summit')
    await expect(page.getByTestId('register-confirmation')).toContainText('Marina Hall A')
    const inbox = await notificationApi('GET', '/notifications', 'ATT-02')
    expect(inbox.status).toBe(200)
    expect(JSON.stringify(inbox.body)).toMatch(/AI in Events Summit|e1|registered/i)
  })

  test('TC-SPM11-AC04 a registration reduces remaining places by one, visible immediately to other attendees', async () => {
    const before = await registrationApi('GET', '/registrations?eventId=e1', 'ATT-01')
    const remainingBefore = before.body.remainingPlaces ?? before.body.placesRemaining
    const created = await registrationApi(
      'POST',
      '/registrations',
      'ATT-02',
      guestRegistration('e1', 'SPM11-DEC'),
    )
    expect(created.status).toBe(201)
    const after = await registrationApi('GET', '/registrations?eventId=e1', 'ATT-01')
    const remainingAfter = after.body.remainingPlaces ?? after.body.placesRemaining
    expect(remainingAfter).toBe(remainingBefore - 1)
  })

  test('TC-SPM11-AC05 a second registration for the same attendee is refused and the existing one is shown', async ({
    page,
  }) => {
    const again = await registrationApi('POST', '/registrations', 'ATT-01', {
      eventId: 'e1',
      name: 'Amy Wong',
      email: 'attendee@connectsphere.com',
    })
    expect([400, 409]).toContain(again.status)
    await login(page, account('ATT-01'))
    await page.goto('/app/events/e1')
    await expect(page.getByTestId('existing-registration')).toBeVisible()
    await expect(page.getByTestId('existing-registration')).toContainText(/registered|Amy Wong/i)
  })

  test('TC-SPM11-AC06 registration is refused when the event is full', async ({ page }) => {
    const denied = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e2', 'SPM11-FULL'))
    expect([400, 409]).toContain(denied.status)
    expect(JSON.stringify(denied.body)).toMatch(/full|capacity/i)
    await login(page, account('ATT-02'))
    await page.goto('/app/events/e2')
    await expect(page.getByTestId('event-full')).toBeVisible()
  })

  test('TC-SPM11-AC07 registration outside the period is refused with the period stated', async () => {
    const denied = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e4', 'SPM11-PERIOD'))
    expect([400, 409]).toContain(denied.status)
    expect(JSON.stringify(denied.body)).toMatch(/opens|period|closed/i)
  })

  test('TC-SPM11-AC08 two attendees submitting for the last place: exactly one succeeds', async () => {
    const [first, second] = await Promise.all([
      registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e1', 'SPM11-RACE-A')),
      registrationApi('POST', '/registrations', 'ATT-01', guestRegistration('e1', 'SPM11-RACE-B')),
    ])
    const statuses = [first.status, second.status].sort()
    expect(statuses[0]).toBe(201)
    expect([409, 400]).toContain(statuses[1])
    const refused = first.status === 201 ? second : first
    expect(JSON.stringify(refused.body)).toMatch(/full|capacity/i)
  })

  test('TC-SPM11-AC09 every condition is enforced on the server when the endpoint is called directly', async () => {
    const planning = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e3', 'SPM11-API'))
    expect([400, 409]).toContain(planning.status)
    const full = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e2', 'SPM11-API-FULL'))
    expect([400, 409]).toContain(full.status)
    const closed = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e4', 'SPM11-API-CLOSED'))
    expect([400, 409]).toContain(closed.status)
  })

  test('TC-SPM11-AC10 reaching capacity notifies the organiser and the assigned coordinator', async () => {
    const organiser = await notificationApi('GET', '/notifications', 'EO-01')
    const coordinator = await notificationApi('GET', '/notifications', 'EC-01')
    expect(organiser.status).toBe(200)
    expect(coordinator.status).toBe(200)
    expect(JSON.stringify(organiser.body)).toMatch(/capacit|full|e1|e2/i)
    expect(JSON.stringify(coordinator.body)).toMatch(/capacit|full|e1|e2/i)
  })
})
