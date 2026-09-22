import { test, expect } from '@playwright/test'
import { authedApi, login } from './support/auth.js'
import { serviceUrls } from './support/api-data.js'
import { account } from './support/test-data.js'

test.describe('SPM-56 Event Organiser dashboard', () => {
  test('TC-SPM56-AC01 open clarifications are shown first', async ({ page }) => {
    await login(page, account('EO-01'))
    const needsReply = page.getByTestId('organiser-section-needs-reply')
    await expect(needsReply).toBeVisible()
    const firstSection = page.locator('[data-testid^="organiser-section-"]').first()
    await expect(firstSection).toHaveAttribute('data-testid', 'organiser-section-needs-reply')
    const item = page.getByTestId('organiser-needs-reply-e3')
    await expect(item).toBeVisible()
    await expect(item).toContainText('Partner Networking Night')
    await expect(item).toContainText(/confirm expected attendance/i)
    await expect(page.getByTestId('organiser-needs-reply-e1')).toHaveCount(0)
  })

  test('TC-SPM56-AC02 events are grouped by plain-language stage', async ({ page }) => {
    await login(page, account('EO-01'))
    await expect(page.getByTestId('organiser-section-awaiting-review')).toBeVisible()
    await expect(page.getByTestId('organiser-section-awaiting-review')).toContainText(/awaiting review/i)
    await expect(page.getByTestId('organiser-event-e6')).toBeVisible()
    await expect(page.getByTestId('organiser-event-e6')).toContainText('Unassigned Client Brief')
    await expect(page.getByTestId('organiser-section-confirmed')).toBeVisible()
    await expect(page.getByTestId('organiser-section-confirmed')).toContainText(/confirmed/i)
    await expect(page.getByTestId('organiser-event-e1')).toBeVisible()
    await expect(page.getByTestId('organiser-section-cancelled')).toBeVisible()
    await expect(page.getByTestId('organiser-section-cancelled')).toContainText(/cancelled/i)
    await expect(page.getByTestId('organiser-event-e8')).toBeVisible()
    await expect(page.getByTestId('organiser-section-submitted')).toHaveCount(0)
    await expect(page.getByTestId('organiser-section-planning')).toHaveCount(0)
    const headings = page.locator('[data-testid^="organiser-section-"] h2, [data-testid^="organiser-section-"] h3')
    const texts = await headings.allTextContents()
    for (const text of texts) {
      expect(text.trim().toLowerCase()).not.toBe('submitted')
      expect(text.trim().toLowerCase()).not.toBe('planning')
    }
  })

  test('TC-SPM56-AC03 pending change requests and outcomes are shown', async ({ page }) => {
    await login(page, account('EO-01'))
    await expect(page.getByTestId('organiser-section-change-requests')).toBeVisible()
    const pending = page.getByTestId('organiser-change-pending')
    await expect(pending).toHaveCount(2)
    await expect(pending).toContainText('New AV change')
    await expect(pending).toContainText('Old date change')
    const outcomes = page.getByTestId('organiser-change-outcome')
    await expect(outcomes.first()).toBeVisible()
    await expect(outcomes).toContainText('Venue date moved')
  })

  test('TC-SPM56-AC04 confirmed upcoming events show venue, date, and time', async ({ page }) => {
    await login(page, account('EO-01'))
    const item = page.getByTestId('organiser-event-e1')
    await expect(item).toBeVisible()
    await expect(item).toContainText('AI in Events Summit')
    await expect(item.getByTestId('organiser-event-e1-venue')).toContainText('Marina Hall A')
    await expect(item.getByTestId('organiser-event-e1-date')).toBeVisible()
    await expect(item.getByTestId('organiser-event-e1-time')).toBeVisible()
  })

  test('TC-SPM56-AC05 new event request is available from the dashboard', async ({ page }) => {
    await login(page, account('EO-01'))
    const start = page.getByTestId('organiser-new-request')
    await expect(start).toBeVisible()
    await start.click()
    await expect(page.locator('#eventName')).toBeVisible()
  })

  test('TC-SPM56-AC06 only the organiser organisation events appear, including colleagues', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await expect(page.getByTestId('organiser-event-e7')).toBeVisible()
    await expect(page.getByTestId('organiser-event-e7')).toContainText('Colleague Town Hall')
    await expect(page.getByTestId('organiser-event-e5')).toHaveCount(0)
    await expect(page.locator('body')).not.toContainText('Beacon Q4 Showcase')

    const ownOrg = await authedApi('GET', `${serviceUrls.event}/events`, 'EO-01')
    expect(ownOrg.status).toBe(200)
    const ownIds = (Array.isArray(ownOrg.body) ? ownOrg.body : []).map((event) => event.eventId)
    expect(ownIds).toContain('e7')
    expect(ownIds).not.toContain('e5')

    const emptyOrg = await authedApi('GET', `${serviceUrls.event}/events`, 'EO-04')
    expect(emptyOrg.status).toBe(200)
    const emptyIds = (Array.isArray(emptyOrg.body) ? emptyOrg.body : []).map((event) => event.eventId)
    expect(emptyIds).not.toContain('e1')
    expect(emptyIds).not.toContain('e7')
  })

  test('TC-SPM56-AC07 empty sections point an organiser with no events at a first request', async ({
    page,
  }) => {
    await login(page, account('EO-04'))
    await expect(page.getByTestId('organiser-needs-reply-empty')).toBeVisible()
    await expect(page.getByTestId('organiser-awaiting-review-empty')).toBeVisible()
    await expect(page.getByTestId('organiser-confirmed-empty')).toBeVisible()
    await expect(page.getByTestId('organiser-cancelled-empty')).toBeVisible()
    await expect(page.getByTestId('organiser-change-requests-empty')).toBeVisible()
    const firstRequest = page.getByTestId('organiser-empty-first-request')
    await expect(firstRequest).toBeVisible()
    await expect(firstRequest).toContainText(/first request|create/i)
  })
})
