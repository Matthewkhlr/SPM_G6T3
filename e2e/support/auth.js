import { expect } from '@playwright/test'

export async function login(page, credentials) {
  await page.goto('/login')
  await page.locator('#username').fill(credentials.email)
  await page.locator('#password').fill(credentials.password)

  const profileResponse = page.waitForResponse(
    (response) => response.url().includes('/users/me') && response.request().method() === 'GET',
  )
  await page.getByRole('button', { name: 'Log in' }).click()
  const response = await profileResponse

  expect(response.status()).toBe(200)
  await expect(page).toHaveURL(/\/app$/)
  await expect(page.locator('.role-label')).toContainText(
    `Signed in as ${credentials.displayName} (${credentials.roleLabel})`,
  )
  return response
}

export async function firebaseIdToken(request, credentials) {
  const apiKey = process.env.VITE_FIREBASE_API_KEY
  if (!apiKey) throw new Error('VITE_FIREBASE_API_KEY is required')

  const response = await request.post(
    `https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${apiKey}`,
    {
      data: {
        email: credentials.email,
        password: credentials.password,
        returnSecureToken: true,
      },
    },
  )
  expect(response.ok(), `Firebase login failed for ${credentials.id}: ${await response.text()}`).toBe(
    true,
  )
  const body = await response.json()
  return body.idToken
}

export function bearer(token) {
  return { Authorization: `Bearer ${token}` }
}
