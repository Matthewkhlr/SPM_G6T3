import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { eventApi } from './support/event.js'

const EVENT = 'e1'

test.describe('SPM-05 Follow-up pending items of the given request', () => {
  test('TC-SPM05-AC01 readiness table shows category, handler, status, assignment date, and attachments', async ({
    page,
  }) => {
    const list = await eventApi('GET', `/${EVENT}/readiness`, 'EC-01')
    expect(list.status).toBe(200)
    expect(list.body.length).toBeGreaterThan(0)
    const row = list.body[0]
    expect(row.category).toBeTruthy()
    expect(row.handlerName || row.personnel).toBeTruthy()
    expect(row.status).toBeTruthy()
    expect(row.assignedAt).toBeTruthy()
    expect(row.attachments).toBeDefined()

    await login(page, account('EC-01'))
    await page.goto(`/app/events/${EVENT}/readiness`)
    const item = page.getByTestId('readiness-row').first()
    await expect(item).toBeVisible()
    await expect(item.getByTestId('readiness-category')).toBeVisible()
    await expect(item.getByTestId('readiness-handler')).toBeVisible()
    await expect(item.getByTestId('readiness-status')).toBeVisible()
    await expect(item.getByTestId('readiness-assigned-at')).toBeVisible()
    await expect(item.getByTestId('readiness-attachments')).toBeVisible()
  })

  test('TC-SPM05-AC02 the coordinator can update a line-item readiness status', async () => {
    const created = await eventApi('POST', `/${EVENT}/readiness-items`, 'EC-01', {
      category: 'venue',
      handlerId: 'u3',
      status: 'outstanding',
    })
    expect(created.status).toBe(201)
    const updated = await eventApi(
      'PATCH',
      `/${EVENT}/readiness-items/${created.body.itemId}`,
      'EC-01',
      { status: 'in_progress' },
    )
    expect(updated.status).toBe(200)
    expect(updated.body.status).toMatch(/in_progress|in progress/i)
  })

  test('TC-SPM05-AC03 assigned personnel contact details are shown for follow-up', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${EVENT}/readiness`)
    const contact = page.getByTestId('readiness-handler-contact').first()
    await expect(contact).toBeVisible()
    await expect(contact).toContainText(/@|phone|\+65/i)
  })

  test('TC-SPM05-AC04 supporting attachments can be opened', async ({ page }) => {
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${EVENT}/readiness`)
    const link = page.getByTestId('readiness-attachment-link').first()
    await expect(link).toBeVisible()
    const href = await link.getAttribute('href')
    expect(href).toBeTruthy()
  })

  test('TC-SPM05-AC05 a line item can be created, changed, and deleted', async () => {
    const created = await eventApi('POST', `/${EVENT}/readiness-items`, 'EC-01', {
      category: 'equipment',
      handlerId: 'u4',
      status: 'outstanding',
      note: 'AUTO-SPM05',
    })
    expect(created.status).toBe(201)
    const changed = await eventApi(
      'PATCH',
      `/${EVENT}/readiness-items/${created.body.itemId}`,
      'EC-01',
      { note: 'AUTO-SPM05-edited' },
    )
    expect(changed.status).toBe(200)
    expect(changed.body.note).toMatch(/edited/)
    const removed = await eventApi(
      'DELETE',
      `/${EVENT}/readiness-items/${created.body.itemId}`,
      'EC-01',
    )
    expect([200, 204]).toContain(removed.status)
    const list = await eventApi('GET', `/${EVENT}/readiness`, 'EC-01')
    expect((list.body || []).map((row) => row.itemId)).not.toContain(created.body.itemId)
  })

  test('TC-SPM05-AC06 saving a line item persists the recorded information', async () => {
    const created = await eventApi('POST', `/${EVENT}/readiness-items`, 'EC-01', {
      category: 'registration',
      handlerId: 'u2',
      status: 'outstanding',
      note: 'AUTO-persist',
    })
    expect(created.status).toBe(201)
    const read = await eventApi(
      'GET',
      `/${EVENT}/readiness-items/${created.body.itemId}`,
      'EC-01',
    )
    expect(read.status).toBe(200)
    expect(read.body.note).toBe('AUTO-persist')
    expect(read.body.category).toBe('registration')
  })

  test('TC-SPM05-AC07 confirming a status requires an explicit confirmation', async ({ page }) => {
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${EVENT}/readiness`)
    await page.getByTestId('readiness-row').first().getByTestId('readiness-confirm-status').click()
    await expect(page.getByTestId('readiness-confirm-dialog')).toBeVisible()
    await page.getByRole('button', { name: /confirm/i }).click()
    await expect(page.getByTestId('readiness-row').first()).toContainText(/confirmed|settled/i)
  })

  test('TC-SPM05-AC08 a line item whose due date is near raises an alert', async () => {
    const soon = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString()
    const created = await eventApi('POST', `/${EVENT}/readiness-items`, 'EC-01', {
      category: 'venue',
      handlerId: 'u3',
      status: 'outstanding',
      dueAt: soon,
    })
    expect(created.status).toBe(201)
    expect(created.body.dueSoon || created.body.alert).toBeTruthy()
    const alerts = await eventApi('GET', `/${EVENT}/readiness?dueSoon=true`, 'EC-01')
    expect(alerts.status).toBe(200)
    expect((alerts.body || []).map((row) => row.itemId)).toContain(created.body.itemId)
  })

  test('TC-SPM05-AC09 an overdue line item is flagged', async () => {
    const past = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString()
    const created = await eventApi('POST', `/${EVENT}/readiness-items`, 'EC-01', {
      category: 'equipment',
      handlerId: 'u4',
      status: 'outstanding',
      dueAt: past,
    })
    expect(created.status).toBe(201)
    expect(created.body.overdue).toBe(true)
    const list = await eventApi('GET', `/${EVENT}/readiness`, 'EC-01')
    const row = (list.body || []).find((item) => item.itemId === created.body.itemId)
    expect(row.overdue).toBe(true)
  })
})
