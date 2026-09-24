import { test, expect } from '@playwright/test'
import { authedApi, login } from './support/auth.js'
import { account } from './support/test-data.js'
import { serviceUrls } from './support/api-data.js'
import { createDraftEvent, eventApi } from './support/event.js'

test.describe('SPM-15 View Event and preparation status', () => {
  test('TC-SPM15-AC01 the organiser sees their organisation events with status and date', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.locator('.nav-item').getByText('My Events', { exact: true }).click()
    const list = page.getByTestId('organiser-event-list')
    await expect(list).toBeVisible()
    const e1 = page.getByTestId('organiser-event-e1')
    await expect(e1).toBeVisible()
    await expect(e1.getByTestId('organiser-event-e1-status')).toBeVisible()
    await expect(e1.getByTestId('organiser-event-e1-date')).toBeVisible()
    await expect(page.getByTestId('organiser-event-e5')).toHaveCount(0)
  })

  test('TC-SPM15-AC02 drafts are distinguishable from submitted events', async ({ page }) => {
    const draftEvent = await createDraftEvent('EO-01', 'AUTO-SPM15-draft')
    await login(page, account('EO-01'))
    await page.locator('.nav-item').getByText('My Events', { exact: true }).click()
    const submitted = page.getByTestId('organiser-event-e6')
    await expect(submitted).toBeVisible()
    await expect(submitted).toHaveAttribute('data-lifecycle', /submitted/i)
    const draft = page.getByTestId(`organiser-event-${draftEvent.eventId}`)
    await expect(draft).toBeVisible()
    await expect(draft).toHaveAttribute('data-lifecycle', /draft|created/i)
    expect(await submitted.getAttribute('data-lifecycle')).not.toBe(
      await draft.getAttribute('data-lifecycle'),
    )
  })

  test('TC-SPM15-AC03 opening an event shows settled and outstanding arrangements in plain language', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e1')
    await expect(page.getByTestId('organiser-arrangements')).toBeVisible()
    await expect(page.getByTestId('organiser-arrangements')).toContainText(/settled|confirmed|in place/i)
    await expect(page.getByTestId('organiser-arrangements')).toContainText(
      /outstanding|still needed|not yet/i,
    )
    const text = await page.getByTestId('organiser-arrangements').innerText()
    expect(text.toLowerCase()).not.toMatch(/\b(submitted|planning)\b/)
  })

  test('TC-SPM15-AC04 items awaiting the organiser are flagged and link to the work', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e3')
    const flag = page.getByTestId('organiser-needs-action')
    await expect(flag).toBeVisible()
    await expect(flag).toContainText(/clarification|change request|needs action/i)
    await flag.click()
    await expect(page).toHaveURL(/clarif|change|e3/i)
  })

  test('TC-SPM15-AC05 the assigned coordinator name and contact are shown', async ({ page }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e1')
    const card = page.getByTestId('organiser-coordinator')
    await expect(card).toBeVisible()
    await expect(card).toContainText('Ben Lee')
    await expect(card).toContainText(/coordinator@connectsphere\.com|@/)
  })

  test('TC-SPM15-AC06 a confirmed event shows venue, date, time, layout, and equipment', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e1')
    const confirmed = page.getByTestId('organiser-confirmed-arrangements')
    await expect(confirmed).toBeVisible()
    await expect(confirmed).toContainText('Marina Hall A')
    await expect(confirmed.getByTestId('organiser-confirmed-date')).toBeVisible()
    await expect(confirmed.getByTestId('organiser-confirmed-time')).toBeVisible()
    await expect(confirmed).toContainText(/theatre|layout/i)
    await expect(confirmed).toContainText(/projector|equipment/i)
  })

  test('TC-SPM15-AC07 the shown status matches the stored event status', async ({ page }) => {
    const stored = await eventApi('GET', '/e1', 'EO-01')
    expect(stored.status).toBe(200)
    await login(page, account('EO-01'))
    await page.goto('/app/events/e1')
    const shown = page.getByTestId('organiser-event-status')
    await expect(shown).toBeVisible()
    await expect(shown).toContainText(new RegExp(stored.body.status, 'i'))
  })

  test('TC-SPM15-AC08 the organiser sees no internal notes, other clients, or unrelated records', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e1')
    const body = await page.locator('body').innerText()
    expect(body).not.toMatch(/Beacon Q4 Showcase|Beacon Media/i)
    expect(body).not.toMatch(/internal note|staff note/i)
    expect(body).not.toMatch(/Skyline Boardroom|Exhibition Hall B/i)

    const event = await authedApi('GET', `${serviceUrls.event}/events/e1`, 'EO-01')
    expect(JSON.stringify(event.body)).not.toMatch(/internalNotes|internal_notes/)
  })

  test('TC-SPM15-AC09 an organiser with no events is pointed at creating a request', async ({
    page,
  }) => {
    await login(page, account('EO-04'))
    await page.locator('.nav-item').getByText('My Events', { exact: true }).click()
    const empty = page.getByTestId('organiser-events-empty')
    await expect(empty).toBeVisible()
    await expect(empty).toContainText(/create|first request|new request/i)
    await expect(page.getByTestId('organiser-empty-create')).toBeVisible()
  })
})
