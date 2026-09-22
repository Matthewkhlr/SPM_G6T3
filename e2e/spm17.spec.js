import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { newVenuePayload } from './support/api-data.js'
import { venueRequest } from './support/venue.js'

function listHasCoreFields(venues) {
  expect(venues.length).toBeGreaterThan(0)
  for (const venue of venues) {
    expect(venue.name).toBeTruthy()
    expect(venue.location).toBeTruthy()
    expect(venue.capacity).toBeGreaterThan(0)
  }
}

test.describe('SPM-17 View venue catalogue', () => {
  test('TC-SPM17-AC01 staff see active venues with name, location, and highest capacity', async () => {
    for (const id of ['EC-01', 'VS-01', 'TS-01']) {
      const list = await venueRequest('GET', '/venues', id)
      expect(list.status, id).toBe(200)
      listHasCoreFields(list.body)
      expect(list.body.some((venue) => venue.venueId === 'v1')).toBe(true)
    }
  })

  test('TC-SPM17-AC02 opening a venue shows address, floor, facilities, accessibility, layouts, hours, and description', async ({
    page,
  }) => {
    const venue = await venueRequest('GET', '/venues/v1', 'EC-01')
    expect(venue.status).toBe(200)
    expect(venue.body.address).toMatch(/HarbourFront/)
    expect(venue.body.floor).toBeTruthy()
    expect(venue.body.facilities.length).toBeGreaterThan(0)
    expect(venue.body.accessibility.length).toBeGreaterThan(0)
    expect(venue.body.layouts[0].name).toBeTruthy()
    expect(venue.body.layouts[0].capacity).toBeGreaterThan(0)
    expect(venue.body.operatingHours.length).toBeGreaterThan(0)
    expect(venue.body.description).toBeTruthy()

    await login(page, account('EC-01'))
    await page.locator('.nav-item').getByText('Venue Catalogue', { exact: true }).click()
    await page.getByText('Marina Hall A', { exact: true }).click()
    await expect(page.locator('.venue-detail')).toContainText('1 HarbourFront Walk')
    await expect(page.locator('.venue-detail')).toContainText('Theatre')
    await expect(page.locator('.venue-detail')).toContainText('Wheelchair accessible')
  })

  test('TC-SPM17-AC03 retired venues are hidden by default and can be filtered back', async ({ page }) => {
    const created = await venueRequest('POST', '/venues', 'VS-01', newVenuePayload('Retired Catalogue Venue'))
    expect(created.status).toBe(201)
    const retired = await venueRequest('POST', `/venues/${created.body.venueId}/retire`, 'VS-01')
    expect(retired.status).toBe(200)

    const hidden = await venueRequest('GET', '/venues', 'EC-01')
    expect(hidden.body.map((row) => row.venueId)).not.toContain(created.body.venueId)
    const shown = await venueRequest('GET', '/venues?includeRetired=true', 'EC-01')
    expect(shown.body.map((row) => row.venueId)).toContain(created.body.venueId)

    await login(page, account('VS-01'))
    await page.locator('.nav-item').getByText('Venue Catalogue', { exact: true }).click()
    await expect(page.getByText('Retired Catalogue Venue')).toHaveCount(0)
    await page.getByLabel(/show retired/i).check()
    await expect(page.getByText('Retired Catalogue Venue')).toBeVisible()
  })

  test('TC-SPM17-AC04 a venue opens its availability calendar', async ({ page }) => {
    await login(page, account('EC-01'))
    await page.locator('.nav-item').getByText('Venue Catalogue', { exact: true }).click()
    await page.getByText('Marina Hall A', { exact: true }).click()
    await page.getByTestId('venue-open-calendar').click()
    await expect(page).toHaveURL(/calendar|availability/i)
    await expect(page.getByTestId('venue-calendar')).toBeVisible()
  })

  test('TC-SPM17-AC05 organisers and attendees cannot reach the catalogue', async ({ page }) => {
    const organiser = await venueRequest('GET', '/venues', 'EO-01')
    expect(organiser.status).toBe(403)
    const attendee = await venueRequest('GET', '/venues', 'ATT-01')
    expect(attendee.status).toBe(403)
    const one = await venueRequest('GET', '/venues/v1', 'EO-01')
    expect(one.status).toBe(403)

    await login(page, account('EO-01'))
    await expect(page.locator('.nav').getByText('Venue Catalogue', { exact: true })).toHaveCount(0)
  })

  test('TC-SPM17-AC06 an empty catalogue explains that Venue Staff maintain it', async ({ page }) => {
    await page.route('**/venues', async (route) => {
      if (route.request().method() === 'GET' && !route.request().url().includes('/venues/v')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: '[]',
        })
        return
      }
      await route.continue()
    })
    await login(page, account('EC-01'))
    await page.locator('.nav-item').getByText('Venue Catalogue', { exact: true }).click()
    await expect(page.getByTestId('venue-catalogue-empty')).toBeVisible()
    await expect(page.getByTestId('venue-catalogue-empty')).toContainText(/venue staff maintain/i)
  })
})
