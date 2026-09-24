import { expect } from '@playwright/test'
import { account } from './test-data.js'

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

export async function firebaseIdToken(_request, credentials) {
  const apiKey = process.env.VITE_FIREBASE_API_KEY
  if (!apiKey) throw new Error('VITE_FIREBASE_API_KEY is required')

  const response = await fetch(
    `https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${apiKey}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: credentials.email,
        password: credentials.password,
        returnSecureToken: true,
      }),
    },
  )
  const body = await response.json()
  expect(response.ok, `Firebase login failed for ${credentials.id}: ${JSON.stringify(body)}`).toBe(
    true,
  )
  expect(body.idToken, `Firebase login for ${credentials.id} returned no idToken`).toBeTruthy()

  const parts = body.idToken.split('.')
  expect(parts.length, `Firebase token for ${credentials.id} is not a JWT`).toBe(3)
  const claims = JSON.parse(Buffer.from(parts[1], 'base64url').toString())
  const now = Math.floor(Date.now() / 1000)
  expect(claims.email, `Firebase token email for ${credentials.id}`).toBe(credentials.email)
  expect(claims.exp, `Firebase token for ${credentials.id} already expired`).toBeGreaterThan(now)
  expect(claims.iat, `Firebase token for ${credentials.id} has iat in the future`).toBeLessThanOrEqual(
    now + 60,
  )
  return body.idToken
}

export function bearer(token) {
  return { Authorization: `Bearer ${token}` }
}

export async function authedApi(method, url, accountId, body) {
  const response = await fetch(url, {
    method,
    headers: {
      ...bearer(await firebaseIdToken(null, account(accountId))),
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}
