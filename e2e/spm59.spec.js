import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'

test.describe('SPM-59 Attendee home', () => {
  test('TC-SPM59-AC01 next upcoming registration is first with date, time, venue, location', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    const next = page.getByTestId('attendee-next-upcoming')
    await expect(next).toBeVisible()
    const changed = page.getByTestId('attendee-registration-e2')
    await expect(changed).toBeVisible()
    const nextBox = await next.boundingBox()
    const changedBox = await changed.boundingBox()
    expect(nextBox.y).toBeLessThan(changedBox.y)
    await expect(next).toContainText('AI in Events Summit')
    await expect(next.getByTestId('attendee-next-upcoming-date')).toBeVisible()
    await expect(next.getByTestId('attendee-next-upcoming-time')).toBeVisible()
    await expect(next.getByTestId('attendee-next-upcoming-venue')).toContainText('Marina Hall A')
    await expect(next.getByTestId('attendee-next-upcoming-location')).toContainText(
      'HarbourFront Centre',
    )
  })

  test('TC-SPM59-AC02 a changed event is flagged as changed', async ({ page }) => {
    await login(page, account('ATT-01'))
    const item = page.getByTestId('attendee-registration-e2')
    await expect(item).toBeVisible()
    await expect(item).toContainText('Venue Ops Workshop')
    await expect(item).toHaveAttribute('data-changed', 'true')
    await expect(item).toContainText(/changed/i)
  })

  test('TC-SPM59-AC03 a cancelled registration is shown as cancelled', async ({ page }) => {
    await login(page, account('ATT-01'))
    const item = page.getByTestId('attendee-registration-e8')
    await expect(item).toBeVisible()
    await expect(item).toContainText('Cancelled Briefing')
    await expect(item).toHaveAttribute('data-cancelled', 'true')
    await expect(item).toContainText(/cancelled/i)
  })

  test('TC-SPM59-AC04 open events appear beneath the attendee registrations', async ({ page }) => {
    await login(page, account('ATT-01'))
    const registrations = page.getByTestId('attendee-section-registrations')
    const open = page.getByTestId('attendee-section-open')
    await expect(registrations).toBeVisible()
    await expect(open).toBeVisible()
    const registrationBox = await registrations.boundingBox()
    const openBox = await open.boundingBox()
    expect(registrationBox).toBeTruthy()
    expect(openBox).toBeTruthy()
    expect(openBox.y).toBeGreaterThan(registrationBox.y)
    await expect(open.getByTestId('attendee-open-e1')).toBeVisible()
  })

  test('TC-SPM59-AC05 no coordinator, internal note, or other attendee identity is shown', async ({
    page,
  }) => {
    await login(page, account('ATT-01'))
    await expect(page.getByTestId('attendee-next-upcoming')).toBeVisible()
    const body = await page.locator('body').innerText()
    expect(body).not.toMatch(/Ben Lee/i)
    expect(body).not.toMatch(/Demo Attendee/i)
    expect(body).not.toMatch(/one@example\.com/i)
    expect(body).not.toMatch(/Please confirm expected attendance/i)
  })

  test('TC-SPM59-AC06 an attendee with no registrations is pointed at browsing events', async ({
    page,
  }) => {
    await login(page, account('ATT-02'))
    const empty = page.getByTestId('attendee-registrations-empty')
    await expect(empty).toBeVisible()
    await expect(empty).toContainText(/brows/i)
    const browse = page.getByTestId('attendee-browse-events')
    await expect(browse).toBeVisible()
    await browse.click()
    await expect(page.locator('.nav').getByText('Browse Events', { exact: true })).toBeVisible()
  })
})
