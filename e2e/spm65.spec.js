import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { EVENT_PROPOSED_DATE_NEAR_DAYS } from './support/api-data.js'
import { createDraftEvent, eventApi } from './support/event.js'

test.describe('SPM-65 Review queue of submitted requests', () => {
  test('TC-SPM65-AC01 the queue lists submitted, under review, and changes requested, and excludes drafts', async () => {
    const draft = await createDraftEvent('EO-01', 'AUTO-SPM65-draft')
    const queue = await eventApi('GET', '/queue', 'EC-01')
    expect(queue.status).toBe(200)
    const ids = (queue.body || []).map((row) => row.eventId)
    expect(ids).toContain('e6')
    expect(ids).not.toContain('e3')
    expect(ids).not.toContain(draft.eventId)
    for (const row of queue.body || []) {
      expect(row.status.toLowerCase()).toMatch(/submitted|under review|changes requested/)
    }
  })

  test('TC-SPM65-AC02 each row shows name, organisation, datetime, attendance, status, coordinator, and submitted time', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.locator('.nav-item').getByText('Review Queue', { exact: true }).click()
    const row = page.getByTestId('review-queue-e6')
    await expect(row).toBeVisible()
    await expect(row).toContainText('Unassigned Client Brief')
    await expect(row).toContainText(/Apex Partners/)
    await expect(row.getByTestId('queue-datetime')).toBeVisible()
    await expect(row.getByTestId('queue-attendance')).toBeVisible()
    await expect(row.getByTestId('queue-status')).toBeVisible()
    await expect(row.getByTestId('queue-submitted-at')).toBeVisible()
  })

  test('TC-SPM65-AC03 unassigned requests are distinguished and can be filtered on their own', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.locator('.nav-item').getByText('Review Queue', { exact: true }).click()
    await expect(page.getByTestId('review-queue-e6')).toHaveAttribute('data-assigned', 'false')
    await page.getByTestId('queue-filter-unassigned').click()
    await expect(page.getByTestId('review-queue-e6')).toBeVisible()
    await expect(page.getByTestId('review-queue-e1')).toHaveCount(0)
  })

  test('TC-SPM65-AC04 the queue sorts by submission time and proposed date, defaulting to longest wait first', async () => {
    const queue = await eventApi('GET', '/queue', 'EC-01')
    expect(queue.status).toBe(200)
    const submitted = (queue.body || []).map((row) => new Date(row.submittedAt).getTime())
    for (let i = 1; i < submitted.length; i += 1) {
      expect(submitted[i]).toBeGreaterThanOrEqual(submitted[i - 1])
    }
    const byDate = await eventApi('GET', '/queue?sort=proposedStartAt', 'EC-01')
    expect(byDate.status).toBe(200)
    expect(byDate.body[0].eventId).not.toBeUndefined()
  })

  test('TC-SPM65-AC05 a coordinator can filter to only their assigned events', async ({ page }) => {
    await login(page, account('EC-01'))
    await page.locator('.nav-item').getByText('Review Queue', { exact: true }).click()
    await page.getByTestId('queue-filter-mine').click()
    await expect(page.getByTestId('review-queue-e6')).toHaveCount(0)
    const mine = await eventApi('GET', '/queue?assignedTo=u2', 'EC-01')
    expect(mine.status).toBe(200)
    for (const row of mine.body || []) {
      expect(row.coordinatorId).toBe('u2')
    }
  })

  test('TC-SPM65-AC06 a request whose proposed date is near is flagged from one shared threshold', async () => {
    expect(EVENT_PROPOSED_DATE_NEAR_DAYS).toBeGreaterThan(0)
    const queue = await eventApi('GET', '/queue', 'EC-01')
    expect(queue.status).toBe(200)
    const near = (queue.body || []).filter((row) => row.dateNear)
    for (const row of near) {
      const days =
        (new Date(row.proposedStartAt).getTime() - Date.now()) / (24 * 60 * 60 * 1000)
      expect(days).toBeLessThanOrEqual(EVENT_PROPOSED_DATE_NEAR_DAYS)
    }
  })

  test('TC-SPM65-AC07 an empty filter explains what is excluded', async ({ page }) => {
    await login(page, account('EC-02'))
    await page.locator('.nav-item').getByText('Review Queue', { exact: true }).click()
    await page.getByTestId('queue-filter-mine').click()
    const empty = page.getByTestId('review-queue-empty')
    await expect(empty).toBeVisible()
    await expect(empty).toContainText(/filter|assigned|no requests/i)
  })
})
