import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { createNameOnlyDraft, eventApi } from './support/event.js'

test.describe('SPM-79 Create and save a draft event request', () => {
  test('TC-SPM79-AC01 the organiser can save a request with only the event name filled in', async () => {
    const created = await createNameOnlyDraft('EO-01', 'AUTO-SPM79-name-only')
    expect(created.eventName).toBe('AUTO-SPM79-name-only')
    expect(created.status).toMatch(/draft|created/i)
  })

  test('TC-SPM79-AC02 a saved draft can be reopened and edited any number of times, and each save keeps prior values', async () => {
    const created = await createNameOnlyDraft('EO-01', 'AUTO-SPM79-edit')
    const first = await eventApi('PATCH', `/${created.eventId}`, 'EO-01', {
      purpose: 'First save',
      category: 'meeting',
    })
    expect(first.status).toBe(200)
    const second = await eventApi('PATCH', `/${created.eventId}`, 'EO-01', {
      description: 'Second save',
    })
    expect(second.status).toBe(200)
    const stored = await eventApi('GET', `/${created.eventId}`, 'EO-01')
    expect(stored.body.eventName).toBe('AUTO-SPM79-edit')
    expect(stored.body.purpose).toBe('First save')
    expect(stored.body.category).toBe('meeting')
    expect(stored.body.description).toBe('Second save')
  })

  test('TC-SPM79-AC03 drafts are labelled Draft, distinct from submitted requests, and have no coordinator, decision, or queue place', async ({
    page,
  }) => {
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM79-label')
    await login(page, account('EO-01'))
    await page.locator('.nav-item').getByText('My Events', { exact: true }).click()
    const row = page.getByTestId(`organiser-event-${draft.eventId}`)
    await expect(row).toBeVisible()
    await expect(row).toHaveAttribute('data-lifecycle', /draft|created/i)
    await expect(row).toContainText(/draft/i)
    expect(draft.coordinatorId || draft.coordinator).toBeFalsy()
    const queue = await eventApi('GET', '/queue', 'EC-01')
    expect((queue.body || []).map((row) => row.eventId)).not.toContain(draft.eventId)
  })

  test('TC-SPM79-AC04 the request captures name, category, purpose, description, date, start and end time, and attendance', async () => {
    const created = await createNameOnlyDraft('EO-01', 'AUTO-SPM79-fields')
    const start = new Date(Date.now() + 20 * 24 * 60 * 60 * 1000)
    const end = new Date(start.getTime() + 2 * 60 * 60 * 1000)
    const saved = await eventApi('PATCH', `/${created.eventId}`, 'EO-01', {
      category: 'workshop',
      purpose: 'Training',
      description: 'Hands-on',
      proposedStartAt: start.toISOString(),
      proposedEndAt: end.toISOString(),
      expectedAttendance: 18,
    })
    expect(saved.status).toBe(200)
    expect(saved.body.category).toBe('workshop')
    expect(saved.body.purpose).toBe('Training')
    expect(saved.body.description).toBe('Hands-on')
    expect(saved.body.expectedAttendance).toBe(18)
    expect(saved.body.proposedStartAt).toBeTruthy()
    expect(saved.body.proposedEndAt).toBeTruthy()
  })

  test('TC-SPM79-AC05 navigating away from an unsaved draft warns that changes will be lost', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.locator('.nav-item').getByText('New Request', { exact: true }).click()
    await page.getByTestId('event-name-input').fill('AUTO-SPM79-unsaved')
    page.once('dialog', async (dialog) => {
      expect(dialog.message()).toMatch(/unsaved|lost/i)
      await dialog.dismiss()
    })
    await page.locator('.nav-item').getByText('My Events', { exact: true }).click()
    await expect(page.getByTestId('unsaved-changes-warning')).toBeVisible()
  })

  test('TC-SPM79-AC06 no internal ConnectSphere user can see or act on a draft before it is submitted', async () => {
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM79-hidden')
    for (const id of ['EC-01', 'VS-01', 'TS-01', 'ATT-01']) {
      const viewed = await eventApi('GET', `/${draft.eventId}`, id)
      expect([403, 404]).toContain(viewed.status)
      const acted = await eventApi('PATCH', `/${draft.eventId}`, id, { purpose: 'nope' })
      expect([403, 404]).toContain(acted.status)
    }
  })
})
