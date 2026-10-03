import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'

test.describe('SPM-55 Event Coordinator dashboard', () => {
  test('TC-SPM55-AC01 unassigned submitted requests show wait time', async ({ page }) => {
    await login(page, account('EC-01'))
    await expect(page.getByTestId('dashboard-section-unassigned')).toBeVisible()
    const item = page.getByTestId('dashboard-unassigned-e6')
    await expect(item).toBeVisible()
    await expect(item).toContainText('Unassigned Client Brief')
    await expect(item.getByTestId('dashboard-unassigned-e6-wait')).toBeVisible()
    await expect(item.getByTestId('dashboard-unassigned-e6-wait')).toContainText(/day/i)
    await expect(page.getByTestId('dashboard-unassigned-e5')).toHaveCount(0)
  })

  test('TC-SPM55-AC02 assigned events show status and outstanding arrangements', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await expect(page.getByTestId('dashboard-section-assigned')).toBeVisible()
    const item = page.getByTestId('dashboard-assigned-e1')
    await expect(item).toBeVisible()
    await expect(item).toContainText('AI in Events Summit')
    await expect(item.getByTestId('dashboard-assigned-e1-status')).toBeVisible()
    await expect(item.getByTestId('dashboard-assigned-e1-outstanding')).toBeVisible()
    await expect(page.getByTestId('dashboard-assigned-e6')).toHaveCount(0)
  })

  test('TC-SPM55-AC03 pending change requests are newest first', async ({ page }) => {
    await login(page, account('EC-01'))
    await expect(page.getByTestId('dashboard-section-change-requests')).toBeVisible()
    const items = page.getByTestId('dashboard-change-request')
    await expect(items).toHaveCount(2)
    await expect(items.nth(0)).toContainText('New AV change')
    await expect(items.nth(1)).toContainText('Old date change')
  })

  test('TC-SPM55-AC04 re-verification items are shown prominently', async ({ page }) => {
    await login(page, account('EC-01'))
    const section = page.getByTestId('dashboard-section-reverification')
    await expect(section).toBeVisible()
    await expect(section).toHaveAttribute('data-priority', 'high')
    const item = page.getByTestId('dashboard-reverification-e2')
    await expect(item).toBeVisible()
    await expect(item).toContainText('Venue Ops Workshop')
  })

  test('TC-SPM55-AC05 each dashboard item opens the work screen', async ({ page }) => {
    await login(page, account('EC-01'))

    await expect(page.getByTestId('dashboard-unassigned-e6')).toBeVisible()
    await page.getByTestId('dashboard-unassigned-e6').click()
    await expect(page).toHaveURL(/e6|review|assign|unassigned/i)
    await page.goto('/app')

    await page.getByTestId('dashboard-assigned-e1').click()
    await expect(page).toHaveURL(/e1|assigned|arrangements/i)
    await page.goto('/app')

    await page.getByTestId('dashboard-change-request').first().click()
    await expect(page).toHaveURL(/change|e1|review/i)
    await page.goto('/app')

    await page.getByTestId('dashboard-reverification-e2').click()
    await expect(page).toHaveURL(/e2|re-?verif|venue|arrangements/i)
  })

  test('TC-SPM55-AC06 lists obey the same access rules as the work screens', async ({ page }) => {
    await login(page, account('EC-02'))
    await expect(page.getByTestId('dashboard-section-unassigned')).toBeVisible()
    await expect(page.getByTestId('dashboard-unassigned-e6')).toBeVisible()
    await expect(page.getByTestId('dashboard-assigned-e1')).toHaveCount(0)
    await expect(page.getByTestId('dashboard-change-request')).toHaveCount(0)
    await expect(page.getByTestId('dashboard-reverification-e2')).toHaveCount(0)
  })

  test('TC-SPM55-AC07 empty sections say there is nothing to do', async ({ page }) => {
    await login(page, account('EC-02'))
    await expect(page.getByTestId('dashboard-assigned-empty')).toBeVisible()
    await expect(page.getByTestId('dashboard-assigned-empty')).toContainText(/nothing to do/i)
    await expect(page.getByTestId('dashboard-change-requests-empty')).toBeVisible()
    await expect(page.getByTestId('dashboard-change-requests-empty')).toContainText(/nothing to do/i)
    await expect(page.getByTestId('dashboard-reverification-empty')).toBeVisible()
    await expect(page.getByTestId('dashboard-reverification-empty')).toContainText(/nothing to do/i)
  })

})
