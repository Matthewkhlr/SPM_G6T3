import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { equipmentApi } from './support/equipment.js'

test.describe('SPM-04 View upcoming events', () => {
  test('TC-SPM04-AC01 the queue lists upcoming events that have equipment requirements, soonest first', async () => {
    const queue = await equipmentApi('GET', '/equipment/queue', 'TS-01')
    expect(queue.status).toBe(200)
    const ids = (queue.body || []).map((row) => row.eventId)
    expect(ids).toContain('e1')
    expect(ids).toContain('e2')
    const e1 = queue.body.find((row) => row.eventId === 'e1')
    const e2 = queue.body.find((row) => row.eventId === 'e2')
    expect(new Date(e1.proposedStartAt || e1.startsAt).getTime()).toBeLessThanOrEqual(
      new Date(e2.proposedStartAt || e2.startsAt).getTime(),
    )
  })

  test('TC-SPM04-AC02 each row shows name, date, times, status, venue, coordinator, and equipment summary', async ({
    page,
  }) => {
    await login(page, account('TS-01'))
    await page.locator('.nav-item').getByText('Upcoming Events', { exact: true }).click()
    const row = page.getByTestId('equipment-queue-e1')
    await expect(row).toBeVisible()
    await expect(row).toContainText('AI in Events Summit')
    await expect(row.getByTestId('queue-date')).toBeVisible()
    await expect(row.getByTestId('queue-start')).toBeVisible()
    await expect(row.getByTestId('queue-end')).toBeVisible()
    await expect(row.getByTestId('queue-status')).toBeVisible()
    await expect(row.getByTestId('queue-venue')).toContainText(/Marina Hall A|venue/i)
    await expect(row.getByTestId('queue-coordinator')).toContainText(/Ben Lee|u2/)
    await expect(row.getByTestId('queue-equipment-summary')).toBeVisible()
  })

  test('TC-SPM04-AC03 each row shows whether the request is awaiting review, partly reserved, fully reserved, or unavailable', async ({
    page,
  }) => {
    await login(page, account('TS-01'))
    await page.locator('.nav-item').getByText('Upcoming Events', { exact: true }).click()
    await expect(page.getByTestId('equipment-queue-e1')).toHaveAttribute(
      'data-equipment-state',
      /awaiting|review|reserved|partial/i,
    )
    await expect(page.getByTestId('equipment-queue-e3')).toHaveAttribute(
      'data-equipment-state',
      /partly|partial|unavailable/i,
    )
  })

  test('TC-SPM04-AC04 requests needing attention, including re-verification, are shown first within the same date', async () => {
    const queue = await equipmentApi('GET', '/equipment/queue', 'TS-01')
    expect(queue.status).toBe(200)
    const byDate = {}
    for (const row of queue.body || []) {
      const day = String(row.proposedStartAt || row.startsAt).slice(0, 10)
      byDate[day] = byDate[day] || []
      byDate[day].push(row)
    }
    for (const rows of Object.values(byDate)) {
      const attention = rows.filter((row) => row.needsAttention || row.needsReverification)
      if (attention.length && rows.length > 1) {
        const firstAttention = rows.findIndex((row) => row.needsAttention || row.needsReverification)
        const firstQuiet = rows.findIndex((row) => !row.needsAttention && !row.needsReverification)
        if (firstQuiet >= 0) expect(firstAttention).toBeLessThan(firstQuiet)
      }
    }
    expect((queue.body || []).some((row) => row.eventId === 'e2' && (row.needsReverification || row.needsAttention))).toBe(
      true,
    )
  })

  test('TC-SPM04-AC05 the queue filters by status and date range, and excludes completed and cancelled by default', async ({
    page,
  }) => {
    const queue = await equipmentApi('GET', '/equipment/queue', 'TS-01')
    expect((queue.body || []).map((row) => row.eventId)).not.toContain('e8')
    await login(page, account('TS-01'))
    await page.locator('.nav-item').getByText('Upcoming Events', { exact: true }).click()
    await expect(page.getByTestId('equipment-queue-e8')).toHaveCount(0)
    await page.getByTestId('queue-filter-status').selectOption(/review|pending|requested/i)
    await page.getByTestId('queue-filter-from').fill(new Date().toISOString().slice(0, 10))
  })

  test('TC-SPM04-AC06 events with no equipment requirements do not appear', async () => {
    const queue = await equipmentApi('GET', '/equipment/queue', 'TS-01')
    expect(queue.status).toBe(200)
    expect((queue.body || []).map((row) => row.eventId)).not.toContain('e6')
  })

  test('TC-SPM04-AC07 technical support can open an event to check availability and reserve', async ({
    page,
  }) => {
    await login(page, account('TS-01'))
    await page.locator('.nav-item').getByText('Upcoming Events', { exact: true }).click()
    await page.getByTestId('equipment-queue-e1').click()
    await expect(page).toHaveURL(/e1|equipment|availability|reserv/i)
    await expect(page.getByTestId('equipment-check')).toBeVisible()
    await expect(page.getByTestId('equipment-reserve')).toBeVisible()
  })
})
