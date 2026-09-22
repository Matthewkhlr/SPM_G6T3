import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'

test.describe('SPM-58 Technical Support Staff dashboard', () => {
  test('TC-SPM58-AC01 equipment requests awaiting review show event and date', async ({
    page,
  }) => {
    await login(page, account('TS-01'))
    await expect(page.getByTestId('tech-section-pending')).toBeVisible()
    const item = page.getByTestId('tech-pending-eq-pending')
    await expect(item).toBeVisible()
    await expect(item).toContainText('AI in Events Summit')
    await expect(item.getByTestId('tech-pending-eq-pending-date')).toBeVisible()
  })

  test('TC-SPM58-AC02 reservations flagged for re-verification are shown', async ({ page }) => {
    await login(page, account('TS-01'))
    await expect(page.getByTestId('tech-section-reverification')).toBeVisible()
    const item = page.getByTestId('tech-reverification-er-e2')
    await expect(item).toBeVisible()
    await expect(item).toContainText('Venue Ops Workshop')
  })

  test('TC-SPM58-AC03 unresolved unavailable or partly fulfilled lines are shown', async ({
    page,
  }) => {
    await login(page, account('TS-01'))
    await expect(page.getByTestId('tech-section-shortfall')).toBeVisible()
    const item = page.getByTestId('tech-shortfall-eq-shortfall')
    await expect(item).toBeVisible()
    await expect(item).toContainText('Partner Networking Night')
    await expect(item).toContainText(/partly fulfilled|unavailable|shortfall/i)
  })

  test('TC-SPM58-AC04 upcoming supplied events are soonest first', async ({ page }) => {
    await login(page, account('TS-01'))
    await expect(page.getByTestId('tech-section-upcoming')).toBeVisible()
    const items = page.getByTestId('tech-upcoming')
    await expect(items).not.toHaveCount(0)
    await expect(items.nth(0)).toContainText('AI in Events Summit')
    await expect(items).toContainText('Venue Ops Workshop')
    const labels = await items.allTextContents()
    expect(labels.findIndex((text) => text.includes('AI in Events Summit'))).toBeLessThan(
      labels.findIndex((text) => text.includes('Venue Ops Workshop')),
    )
  })

  test('TC-SPM58-AC05 each item opens the work screen', async ({ page }) => {
    await login(page, account('TS-01'))

    await expect(page.getByTestId('tech-pending-eq-pending')).toBeVisible()
    await page.getByTestId('tech-pending-eq-pending').click()
    await expect(page).toHaveURL(/equipment|reservation|eq-pending|request/i)
    await page.goto('/app')

    await page.getByTestId('tech-reverification-er-e2').click()
    await expect(page).toHaveURL(/equipment|reservation|er-e2|re-?verif/i)
    await page.goto('/app')

    await page.getByTestId('tech-shortfall-eq-shortfall').click()
    await expect(page).toHaveURL(/equipment|reservation|eq-shortfall|shortfall/i)
    await page.goto('/app')

    await page.getByTestId('tech-upcoming').first().click()
    await expect(page).toHaveURL(/equipment|reservation|e1|upcoming/i)
  })

  test('TC-SPM58-AC06 lists obey the same access rules as the work screens', async ({ page }) => {
    await login(page, account('TS-01'))
    await expect(page.getByTestId('tech-pending-eq-pending')).toBeVisible()
    await page.getByRole('button', { name: 'Log out' }).click()
    await login(page, account('EO-01'))
    await expect(page.getByTestId('tech-pending-eq-pending')).toHaveCount(0)
    await expect(page.getByTestId('tech-section-pending')).toHaveCount(0)
  })

  test('TC-SPM58-AC07 each section has an empty state', async ({ page }) => {
    await login(page, account('TS-02'))
    await expect(page.getByTestId('tech-pending-empty')).toBeVisible()
    await expect(page.getByTestId('tech-reverification-empty')).toBeVisible()
    await expect(page.getByTestId('tech-shortfall-empty')).toBeVisible()
    await expect(page.getByTestId('tech-upcoming-empty')).toBeVisible()
  })
})
