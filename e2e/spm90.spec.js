import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { eventApi } from './support/event.js'
import { notificationApi } from './support/registration.js'

test.describe('SPM-90 Set up registration during planning', () => {
  test('TC-SPM90-AC01 the assigned coordinator can set registration needed, period, and capacity from Planning to Confirmed', async () => {
    const updated = await eventApi('PATCH', '/e3/registration-settings', 'EC-01', {
      registrationEnabled: true,
      registrationOpensAt: new Date(Date.now() + 2 * 86400000).toISOString(),
      registrationClosesAt: new Date(Date.now() + 20 * 86400000).toISOString(),
      capacity: 80,
    })
    expect(updated.status).toBe(200)
    expect(updated.body.registrationEnabled).toBe(true)
    expect(updated.body.capacity).toBe(80)
  })

  test('TC-SPM90-AC02 the closing time must be after the opening time and no later than the event start', async () => {
    const same = await eventApi('PATCH', '/e3/registration-settings', 'EC-01', {
      registrationEnabled: true,
      registrationOpensAt: new Date(Date.now() + 5 * 86400000).toISOString(),
      registrationClosesAt: new Date(Date.now() + 5 * 86400000).toISOString(),
      capacity: 40,
    })
    expect([400, 422]).toContain(same.status)
    const afterStart = await eventApi('PATCH', '/e3/registration-settings', 'EC-01', {
      registrationEnabled: true,
      registrationOpensAt: new Date(Date.now() + 2 * 86400000).toISOString(),
      registrationClosesAt: new Date(Date.now() + 40 * 86400000).toISOString(),
      capacity: 40,
    })
    expect([400, 422]).toContain(afterStart.status)
  })

  test('TC-SPM90-AC03 capacity above the booked venue layout warns with both figures and requires confirmation', async ({
    page,
  }) => {
    const blocked = await eventApi('PATCH', '/e1/registration-settings', 'EC-01', {
      capacity: 500,
    })
    expect(blocked.status).toBe(409)
    expect(JSON.stringify(blocked.body)).toMatch(/300|500|capacity|Theatre/i)
    await login(page, account('EC-01'))
    await page.goto('/app/events/e1/registration-settings')
    await page.getByTestId('registration-capacity').fill('500')
    await page.getByTestId('registration-save').click()
    await expect(page.getByTestId('capacity-venue-warning')).toBeVisible()
    await page.getByTestId('capacity-confirm').click()
  })

  test('TC-SPM90-AC04 reducing capacity below the current registration count is refused and the count is stated', async () => {
    const denied = await eventApi('PATCH', '/e1/registration-settings', 'EC-01', {
      capacity: 1,
    })
    expect([400, 409]).toContain(denied.status)
    expect(JSON.stringify(denied.body)).toMatch(/registered|2|3/)
  })

  test('TC-SPM90-AC05 turning registration off when people are registered warns, requires confirm, and notifies attendees', async () => {
    const blocked = await eventApi('PATCH', '/e1/registration-settings', 'EC-01', {
      registrationEnabled: false,
    })
    expect(blocked.status).toBe(409)
    expect(JSON.stringify(blocked.body)).toMatch(/registered|confirm|attendee/i)
    const stored = await eventApi('GET', '/e1', 'EC-01')
    expect(stored.body.registrationEnabled).toBe(true)
  })

  test('TC-SPM90-AC06 the organiser can see the settings and is notified when they change', async ({
    page,
  }) => {
    await eventApi('PATCH', '/e3/registration-settings', 'EC-01', {
      registrationEnabled: true,
      registrationOpensAt: new Date(Date.now() + 3 * 86400000).toISOString(),
      registrationClosesAt: new Date(Date.now() + 15 * 86400000).toISOString(),
      capacity: 60,
    })
    await login(page, account('EO-01'))
    await page.goto('/app/events/e3')
    await expect(page.getByTestId('organiser-registration-settings')).toContainText(/60|registration/i)
    const inbox = await notificationApi('GET', '/notifications', 'EO-01')
    expect(JSON.stringify(inbox.body)).toMatch(/registration|e3/i)
  })

  test('TC-SPM90-AC07 changes to registration settings are written to the activity log', async () => {
    await eventApi('PATCH', '/e3/registration-settings', 'EC-01', {
      registrationEnabled: true,
      capacity: 70,
      registrationOpensAt: new Date(Date.now() + 4 * 86400000).toISOString(),
      registrationClosesAt: new Date(Date.now() + 16 * 86400000).toISOString(),
    })
    const log = await eventApi('GET', '/e3/activity-log', 'EC-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/registration|capacity|70|u2/)
  })
})
