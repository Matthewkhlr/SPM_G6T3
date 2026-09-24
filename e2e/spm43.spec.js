import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import {
  account,
  expectedTabs,
  invalidCredentials,
  validCredentials,
} from './support/test-data.js'
import { serviceUrls } from './support/api-data.js'

test.describe('SPM-43 User Login and Session Management', () => {
  test.describe('TC-SPM43-AC01 valid credentials and role landing', () => {
    for (const credentials of validCredentials) {
      test(`${credentials.id} reaches the correct role home`, async ({ page }) => {
        const response = await login(page, credentials)
        const profile = await response.json()

        expect(profile.userName).toBe(credentials.displayName)
        expect(profile.email).toBe(credentials.email)
        for (const tab of expectedTabs[credentials.id]) {
          await expect(page.locator('.nav').getByText(tab, { exact: true })).toBeVisible()
        }
      })
    }
  })

  test('TC-SPM43-AC02 valid credentials establish a persistent session', async ({ page }) => {
    const credentials = account('EO-01')
    let authorization
    page.on('request', (request) => {
      if (request.url().includes('/users/me')) {
        authorization = request.headers().authorization
      }
    })

    await login(page, credentials)
    expect(authorization).toMatch(/^Bearer \S+/)

    const restoredProfile = page.waitForResponse(
      (response) => response.url().includes('/users/me') && response.status() === 200,
    )
    await page.reload()
    await restoredProfile
    await expect(page).toHaveURL(/\/app$/)
    await expect(page.locator('.role-label')).toContainText(credentials.displayName)

    await page.goto('/login')
    await expect(page).toHaveURL(/\/app$/)
  })

  test.describe('TC-SPM43-AC03 invalid credentials', () => {
    for (const credentials of invalidCredentials) {
      test(`${credentials.id} is rejected without revealing account existence`, async ({ page }) => {
        let profileCalls = 0
        page.on('request', (request) => {
          if (request.url().includes('/users/me')) profileCalls += 1
        })

        await page.goto('/login')
        await page.locator('#username').fill(credentials.email)
        await page.locator('#password').fill(credentials.password)
        await page.getByRole('button', { name: 'Log in' }).click()

        await expect(page.locator('.auth-error')).toHaveText('Invalid email or password.')
        await expect(page).toHaveURL(/\/login$/)
        expect(profileCalls).toBe(0)

        await page.goto('/app')
        await expect(page).toHaveURL(/\/login$/)
        await expect(page.locator('.role-label')).toHaveCount(0)
      })
    }
  })

  const emptyCases = [
    {
      id: 'EMP-01',
      email: '',
      password: '',
      errors: ['Email is required.', 'Password is required.'],
    },
    {
      id: 'EMP-02',
      email: '',
      password: 'organiser123',
      errors: ['Email is required.'],
    },
    {
      id: 'EMP-03',
      email: 'organiser@connectsphere.com',
      password: '',
      errors: ['Password is required.'],
    },
  ]

  test.describe('TC-SPM43-AC04 empty-field validation', () => {
    for (const row of emptyCases) {
      test(`${row.id} blocks authentication requests`, async ({ page }) => {
        const authRequests = []
        page.on('request', (request) => {
          if (
            request.url().includes('identitytoolkit.googleapis.com') ||
            request.url().includes('/users/me')
          ) {
            authRequests.push(request.url())
          }
        })

        await page.goto('/login')
        if (row.email) await page.locator('#username').fill(row.email)
        if (row.password) await page.locator('#password').fill(row.password)
        await page.getByRole('button', { name: 'Log in' }).click()

        for (const message of row.errors) {
          await expect(page.locator('.field-error').getByText(message)).toBeVisible()
        }
        await expect(page.locator('.field-error')).toHaveCount(row.errors.length)
        await expect(page.locator('.auth-error')).toHaveCount(0)
        await expect(page).toHaveURL(/\/login$/)
        await page.waitForTimeout(250)
        expect(authRequests).toEqual([])
      })
    }
  })

  test('TC-SPM43-AC05 protected page redirects and protected API returns 401', async ({
    page,
    request,
  }) => {
    await page.goto('/app')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.locator('.shell')).toHaveCount(0)

    const missingToken = await request.get(`${serviceUrls.user}/users/me`)
    expect(missingToken.status()).toBe(401)

    const invalidToken = await request.get(`${serviceUrls.user}/users/me`, {
      headers: { Authorization: 'Bearer not-a-real-token' },
    })
    expect(invalidToken.status()).toBe(401)
  })

  test('TC-SPM43-AC06 logout prevents browser-back access to protected views', async ({ page }) => {
    await login(page, account('EO-01'))
    await page.getByRole('button', { name: 'Log out' }).click()
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.locator('.shell')).toHaveCount(0)

    await page.goBack()
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.locator('.shell')).toHaveCount(0)

    await page.goto('/app')
    await expect(page).toHaveURL(/\/login$/)
  })

  test('TC-SPM43-AC07 password is masked during entry', async ({ page }) => {
    await page.goto('/login')
    const password = page.locator('#password')

    await expect(password).toHaveAttribute('type', 'password')
    await password.fill('MaskCheck123')
    await expect(password).toHaveAttribute('type', 'password')

    await page.getByRole('button', { name: 'Show password' }).click()
    await expect(password).toHaveAttribute('type', 'text')
    await expect(password).toHaveValue('MaskCheck123')

    await page.getByRole('button', { name: 'Hide password' }).click()
    await expect(password).toHaveAttribute('type', 'password')
    await expect(page).toHaveURL(/\/login$/)
  })
})
