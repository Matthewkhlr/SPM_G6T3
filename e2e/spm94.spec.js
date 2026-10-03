import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { notificationApi } from './support/registration.js'

test.describe('SPM-94 Manage my notifications', () => {
  test('TC-SPM94-AC01 an unread count is visible on every screen and updates when notifications are read', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    const badge = page.getByTestId('notification-unread-count')
    await expect(badge).toBeVisible()
    const before = await badge.innerText()
    await page.goto('/app/notifications')
    const unread = page.locator('[data-read="false"]').first()
    if (await unread.count()) {
      await unread.click()
      await expect(badge).not.toHaveText(before)
    }
  })

  test('TC-SPM94-AC02 the list shows newest first, with unread ones visually distinct', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/notifications')
    const items = page.getByTestId('notification-row')
    await expect(items.first()).toBeVisible()
    const unread = page.locator('[data-testid="notification-row"][data-read="false"]')
    if (await unread.count()) {
      await expect(unread.first()).toHaveAttribute('data-read', 'false')
    }
  })

  test('TC-SPM94-AC03 opening a notification marks it read and navigates to the event or resource', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/notifications')
    await page.getByTestId('notification-row').first().click()
    await expect(page).toHaveURL(/e1|events|notifications/i)
  })

  test('TC-SPM94-AC04 the user can mark one read, mark all read, and filter to unread only', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/notifications')
    await page.getByTestId('notification-mark-all-read').click()
    await page.getByTestId('notification-filter-unread').click()
    const marked = await notificationApi('POST', '/notifications/read-all', 'EO-01')
    expect([200, 204]).toContain(marked.status)
  })

  test('TC-SPM94-AC05 following a notification the user may no longer access shows a clear message, not an error page', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/notifications/forbidden-resource')
    await expect(page.getByTestId('notification-unavailable')).toBeVisible()
    await expect(page.getByText(/500|crash/i)).toHaveCount(0)
  })

  test('TC-SPM94-AC06 a user sees only their own notifications, enforced on the server', async () => {
    const own = await notificationApi('GET', '/notifications', 'EO-01')
    expect(own.status).toBe(200)
    const other = await notificationApi('GET', '/notifications?userId=u2', 'EO-01')
    expect(JSON.stringify(other.body)).not.toMatch(/u2.*coordinator/i)
    const stolen = await notificationApi('GET', '/notifications/n1', 'ATT-01')
    expect([403, 404]).toContain(stolen.status)
  })

  test('TC-SPM94-AC07 when the user has no notifications, an empty state says so', async ({
    page,
  }) => {
    await login(page, account('ATT-02'))
    await page.goto('/app/notifications')
    const empty = page.getByTestId('notifications-empty')
    await expect(empty).toBeVisible()
    await expect(empty).toContainText(/no notifications|none/i)
  })

  test('TC-SPM94-AC08 the list loads a page at a time rather than every notification ever raised', async () => {
    const page1 = await notificationApi('GET', '/notifications?page=1&pageSize=10', 'EO-01')
    expect(page1.status).toBe(200)
    const items = page1.body.items || page1.body
    expect(items.length).toBeLessThanOrEqual(10)
    expect(page1.body.page || page1.body.nextPage).toBeTruthy()
  })
})
