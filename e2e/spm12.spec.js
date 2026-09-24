import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { guestRegistration, notificationApi, registrationApi } from './support/registration.js'

test.describe('SPM-12 Registration withdrawal', () => {
  test('TC-SPM12-AC01 the attendee can withdraw only from an event they are currently registered for', async () => {
    const own = await registrationApi('POST', '/registrations/r-att-e2/withdraw', 'ATT-01')
    expect([200, 409]).toContain(own.status)
    const others = await registrationApi('POST', '/registrations/r1/withdraw', 'ATT-01')
    expect([403, 404]).toContain(others.status)
  })

  test('TC-SPM12-AC02 withdrawal is permitted while the event has not started and is not completed or cancelled', async () => {
    const created = await registrationApi(
      'POST',
      '/registrations',
      'ATT-02',
      guestRegistration('e1', 'SPM12-OK'),
    )
    if (created.status === 201) {
      const withdrawn = await registrationApi(
        'POST',
        `/registrations/${created.body.attendeeRegistrationId}/withdraw`,
        'ATT-02',
      )
      expect(withdrawn.status).toBe(200)
    }
    const cancelled = await registrationApi('POST', '/registrations/r-att-e8/withdraw', 'ATT-01')
    expect([400, 403, 409]).toContain(cancelled.status)
  })

  test('TC-SPM12-AC03 withdrawing asks for confirmation naming the event', async ({ page }) => {
    await login(page, account('ATT-01'))
    await page.goto('/app/registrations/r-att-e1')
    await page.getByTestId('registration-withdraw').click()
    const dialog = page.getByTestId('withdraw-confirm')
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText('AI in Events Summit')
  })

  test('TC-SPM12-AC04 the registration becomes withdrawn and the record is kept', async () => {
    const created = await registrationApi(
      'POST',
      '/registrations',
      'ATT-02',
      guestRegistration('e1', 'SPM12-KEEP'),
    )
    expect(created.status).toBe(201)
    const withdrawn = await registrationApi(
      'POST',
      `/registrations/${created.body.attendeeRegistrationId}/withdraw`,
      'ATT-02',
    )
    expect(withdrawn.status).toBe(200)
    expect(withdrawn.body.status).toMatch(/withdrawn/i)
    const viewed = await registrationApi(
      'GET',
      `/registrations/${created.body.attendeeRegistrationId}`,
      'ATT-02',
    )
    expect(viewed.status).toBe(200)
    expect(viewed.body.status).toMatch(/withdrawn/i)
  })

  test('TC-SPM12-AC05 the place is released immediately, raising remaining places by one', async () => {
    const created = await registrationApi(
      'POST',
      '/registrations',
      'ATT-02',
      guestRegistration('e1', 'SPM12-FREE'),
    )
    expect(created.status).toBe(201)
    const before = await registrationApi('GET', '/registrations?eventId=e1', 'ATT-01')
    await registrationApi(
      'POST',
      `/registrations/${created.body.attendeeRegistrationId}/withdraw`,
      'ATT-02',
    )
    const after = await registrationApi('GET', '/registrations?eventId=e1', 'ATT-01')
    const remainingBefore = before.body.remainingPlaces ?? before.body.placesRemaining
    const remainingAfter = after.body.remainingPlaces ?? after.body.placesRemaining
    expect(remainingAfter).toBe(remainingBefore + 1)
  })

  test('TC-SPM12-AC06 the attendee is shown confirmation and notified of the withdrawal', async ({
    page,
  }) => {
    const created = await registrationApi(
      'POST',
      '/registrations',
      'ATT-02',
      guestRegistration('e1', 'SPM12-NOTE'),
    )
    expect(created.status).toBe(201)
    await registrationApi(
      'POST',
      `/registrations/${created.body.attendeeRegistrationId}/withdraw`,
      'ATT-02',
    )
    await login(page, account('ATT-02'))
    await page.goto(`/app/registrations/${created.body.attendeeRegistrationId}`)
    await expect(page.getByTestId('withdraw-confirmation')).toContainText(/withdrawn/i)
    const inbox = await notificationApi('GET', '/notifications', 'ATT-02')
    expect(JSON.stringify(inbox.body)).toMatch(/withdrawn|e1/i)
  })

  test('TC-SPM12-AC07 the attendee can register again later while the period is open and a place remains', async () => {
    const first = await registrationApi(
      'POST',
      '/registrations',
      'ATT-02',
      guestRegistration('e1', 'SPM12-AGAIN'),
    )
    expect(first.status).toBe(201)
    await registrationApi(
      'POST',
      `/registrations/${first.body.attendeeRegistrationId}/withdraw`,
      'ATT-02',
    )
    const again = await registrationApi('POST', '/registrations', 'ATT-02', {
      eventId: 'e1',
      name: first.body.attendeeName,
      email: first.body.attendeeEmail,
    })
    expect(again.status).toBe(201)
  })

  test('TC-SPM12-AC08 withdrawal is unavailable after the event has started, completed, or been cancelled', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    await page.goto('/app/registrations/r-att-e8')
    await expect(page.getByTestId('registration-withdraw')).toHaveCount(0)
    const denied = await registrationApi('POST', '/registrations/r-att-e8/withdraw', 'ATT-01')
    expect([400, 403, 409]).toContain(denied.status)
  })

  test('TC-SPM12-AC09 the organiser and assigned coordinator can see the withdrawal in the registration list', async () => {
    const created = await registrationApi(
      'POST',
      '/registrations',
      'ATT-02',
      guestRegistration('e1', 'SPM12-LIST'),
    )
    expect(created.status).toBe(201)
    await registrationApi(
      'POST',
      `/registrations/${created.body.attendeeRegistrationId}/withdraw`,
      'ATT-02',
    )
    const asOrganiser = await registrationApi('GET', '/registrations?eventId=e1&includeWithdrawn=true', 'EO-01')
    expect(asOrganiser.status).toBe(200)
    expect(JSON.stringify(asOrganiser.body)).toMatch(/withdrawn/)
    const asCoord = await registrationApi('GET', '/registrations?eventId=e1&includeWithdrawn=true', 'EC-01')
    expect(asCoord.status).toBe(200)
    expect(JSON.stringify(asCoord.body)).toMatch(/withdrawn/)
  })
})
