import { execSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect } from '@playwright/test'
import { account } from './support/test-data.js'
import { bearer, firebaseIdToken } from './support/auth.js'
import { serviceUrls } from './support/api-data.js'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

const TEXT_FILE = /\.(env.*|example|gitignore|js|json|md|py|txt|toml|yml|yaml)$/i

function trackedFiles() {
  return execSync('git ls-files', { cwd: ROOT, encoding: 'utf8' })
    .split(/\r?\n/)
    .filter(Boolean)
}

function unsignedJwt(claims) {
  const header = Buffer.from(JSON.stringify({ alg: 'RS256', typ: 'JWT' })).toString('base64url')
  const payload = Buffer.from(JSON.stringify(claims)).toString('base64url')
  return `${header}.${payload}.not-a-real-signature`
}

function expiredToken() {
  const now = Math.floor(Date.now() / 1000)
  return unsignedJwt({
    sub: 'expired-uid',
    email: account('EO-01').email,
    iat: now - 7200,
    exp: now - 3600,
  })
}

function tamperedToken(validToken) {
  const [header, payload, signature] = validToken.split('.')
  const claims = JSON.parse(Buffer.from(payload, 'base64url').toString())
  claims.email = `tampered-${claims.email}`
  return `${header}.${Buffer.from(JSON.stringify(claims)).toString('base64url')}.${signature}`
}

function probes() {
  return [
    { name: 'user', method: 'GET', url: `${serviceUrls.user}/users/me` },
    { name: 'event', method: 'GET', url: `${serviceUrls.event}/events` },
    { name: 'venue', method: 'GET', url: `${serviceUrls.venue}/venues` },
    { name: 'equipment', method: 'GET', url: `${serviceUrls.equipment}/equipment` },
    {
      name: 'registration',
      method: 'GET',
      url: `${serviceUrls.registration}/registrations?eventId=e1`,
    },
    {
      name: 'notification',
      method: 'POST',
      url: `${serviceUrls.notification}/notifications`,
      body: {
        to: account('EO-01').email,
        subject: 'SPM-51 auth probe',
        body: 'Token verification check.',
      },
    },
  ]
}

async function call(probe, token) {
  const response = await fetch(probe.url, {
    method: probe.method,
    headers: {
      ...(token ? bearer(token) : {}),
      'Content-Type': 'application/json',
    },
    body: probe.body === undefined ? undefined : JSON.stringify(probe.body),
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

test.describe('SPM-51 Set up Firebase Authentication', () => {
  test('TC-SPM51-AC01 Firebase credentials are never committed to source control', () => {
    const gitignore = fs.readFileSync(path.join(ROOT, '.gitignore'), 'utf8')
    expect(gitignore).toMatch(/^\.env$/m)
    expect(gitignore).toMatch(/firebase-adminsdk/)

    const tracked = trackedFiles()
    const banned = tracked.filter(
      (file) =>
        file === '.env' ||
        /(^|\/)\.env$/.test(file) ||
        /firebase-adminsdk/i.test(file) ||
        /serviceAccountKey/i.test(file) ||
        /google-services\.json$/i.test(file),
    )
    expect(banned, banned.join(', ')).toEqual([])

    for (const file of tracked) {
      if (!TEXT_FILE.test(file) && path.basename(file) !== '.env') continue
      const text = fs.readFileSync(path.join(ROOT, file), 'utf8')
      expect(text, file).not.toMatch(/BEGIN PRIVATE KEY/)
      expect(text, file).not.toMatch(/"type"\s*:\s*"service_account"/)
    }
  })

  test('TC-SPM51-AC02 every backend service independently verifies the Firebase login token', async () => {
    const valid = await firebaseIdToken(null, account('EO-01'))
    for (const probe of probes()) {
      const missing = await call(probe)
      expect(missing.status, `${probe.name} missing token`).toBe(401)
      const invalid = await call(probe, 'not-a-real-token')
      expect(invalid.status, `${probe.name} invalid token`).toBe(401)
      const authed = await call(probe, valid)
      expect(authed.status, `${probe.name} valid token`).not.toBe(401)
    }
  })

  test('TC-SPM51-AC03 each Firebase identity maps to exactly one user record', async () => {
    const first = await call({ method: 'GET', url: `${serviceUrls.user}/users/me` }, await firebaseIdToken(null, account('EO-01')))
    expect(first.status).toBe(200)
    expect(first.body.userId).toBe('u1')
    expect(first.body.userName).toBe('Alice Tan')
    expect(first.body.email).toBe(account('EO-01').email)

    const second = await call({ method: 'GET', url: `${serviceUrls.user}/users/me` }, await firebaseIdToken(null, account('EO-01')))
    expect(second.status).toBe(200)
    expect(second.body.userId).toBe('u1')
    expect(second.body.email).toBe(account('EO-01').email)

    const directory = await call({ method: 'GET', url: `${serviceUrls.user}/users` }, await firebaseIdToken(null, account('EO-01')))
    expect(directory.status).toBe(200)
    const matches = directory.body.filter((row) => row.email === account('EO-01').email)
    expect(matches).toHaveLength(1)
    expect(matches[0].userId).toBe('u1')
  })

  test('TC-SPM51-AC04 invalid, expired, and tampered tokens are rejected the same way', async () => {
    const valid = await firebaseIdToken(null, account('EO-01'))
    const tokens = {
      invalid: 'not-a-real-token',
      expired: expiredToken(),
      tampered: tamperedToken(valid),
    }
    const endpoints = [
      { method: 'GET', url: `${serviceUrls.user}/users/me` },
      { method: 'GET', url: `${serviceUrls.event}/events` },
    ]

    for (const endpoint of endpoints) {
      const results = {}
      for (const [reason, token] of Object.entries(tokens)) {
        results[reason] = await call(endpoint, token)
        expect(results[reason].status, `${endpoint.url} ${reason}`).toBe(401)
      }
      expect(results.expired.body).toEqual(results.invalid.body)
      expect(results.tampered.body).toEqual(results.invalid.body)
      expect(JSON.stringify(results.invalid.body)).not.toMatch(/signature|malformed|clock/i)
    }
  })
})
