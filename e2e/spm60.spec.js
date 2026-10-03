import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { newVenuePayload } from './support/api-data.js'
import { venueRequest } from './support/venue.js'

test.describe('SPM-60 Maintain venue records and supported layouts', () => {
  test('TC-SPM60-AC01 a venue record holds the published fields', async () => {
    const venue = await venueRequest('GET', '/venues/v1', 'VS-01')
    expect(venue.status).toBe(200)
    for (const field of [
      'code',
      'name',
      'location',
      'address',
      'floor',
      'facilities',
      'accessibility',
      'operatingHours',
      'description',
    ]) {
      expect(venue.body[field], field).toBeTruthy()
    }
    expect(venue.body.operatingHours[0].day).toBeTruthy()
    expect(venue.body.operatingHours[0].opens).toBeTruthy()
    expect(venue.body.operatingHours[0].closes).toBeTruthy()
  })

  test('TC-SPM60-AC02 each venue records supported layouts with a capacity', async () => {
    const venue = await venueRequest('GET', '/venues/v1', 'VS-01')
    expect(venue.body.layouts.length).toBeGreaterThan(0)
    for (const layout of venue.body.layouts) {
      expect(layout.name).toBeTruthy()
      expect(layout.capacity).toBeGreaterThan(0)
    }
  })

  test('TC-SPM60-AC03 overall capacity is the highest layout capacity', async () => {
    const venue = await venueRequest('GET', '/venues/v1', 'VS-01')
    const highest = Math.max(...venue.body.layouts.map((layout) => layout.capacity))
    expect(venue.body.capacity).toBe(highest)
  })

  test('TC-SPM60-AC04 venue staff can add, edit, and retire a venue without deleting history', async () => {
    const created = await venueRequest('POST', '/venues', 'VS-01', newVenuePayload('Maintain Add Venue'))
    expect(created.status).toBe(201)
    const updated = await venueRequest('PATCH', `/venues/${created.body.venueId}`, 'VS-01', {
      description: 'Edited by SPM-60',
    })
    expect(updated.status).toBe(200)
    expect(updated.body.description).toBe('Edited by SPM-60')

    const retired = await venueRequest('POST', `/venues/${created.body.venueId}/retire`, 'VS-01')
    expect(retired.status).toBe(200)
    expect(retired.body.isActive).toBe(false)
    const hidden = await venueRequest('GET', '/venues', 'VS-01')
    expect(hidden.body.map((row) => row.venueId)).not.toContain(created.body.venueId)
    const stillThere = await venueRequest('GET', `/venues/${created.body.venueId}`, 'VS-01')
    expect(stillThere.status).toBe(200)
    expect(stillThere.body.isActive).toBe(false)
  })

  test('TC-SPM60-AC05 retiring a venue with a confirmed future booking warns and lists events', async ({
    page,
  }) => {
    const blocked = await venueRequest('POST', '/venues/v1/retire', 'VS-01')
    expect(blocked.status).toBe(409)
    expect(JSON.stringify(blocked.body)).toMatch(/confirmed upcoming|e1|e2/i)

    await login(page, account('VS-01'))
    await page.locator('.nav-item').getByText('Venue Catalogue', { exact: true }).click()
    await page.getByText('Marina Hall A', { exact: true }).click()
    await page.getByRole('button', { name: 'Retire' }).click()
    await page.getByRole('button', { name: 'Yes, retire' }).click()
    await expect(page.locator('.retire-warning')).toBeVisible()
    await expect(page.locator('.retire-warning')).toContainText(/confirmed upcoming/i)
  })

  test('TC-SPM60-AC06 zero or negative layout capacity is rejected', async () => {
    const created = await venueRequest('POST', '/venues', 'VS-01', newVenuePayload('Capacity Guard'))
    expect(created.status).toBe(201)
    const zero = await venueRequest('PATCH', `/venues/${created.body.venueId}`, 'VS-01', {
      layouts: [{ name: 'Theatre', capacity: 0 }],
    })
    expect([400, 422]).toContain(zero.status)
    const negative = await venueRequest('PATCH', `/venues/${created.body.venueId}`, 'VS-01', {
      layouts: [{ name: 'Theatre', capacity: -4 }],
    })
    expect([400, 422]).toContain(negative.status)
  })

  test('TC-SPM60-AC07 only venue staff can change records; other roles are read-only', async () => {
    const read = await venueRequest('GET', '/venues/v1', 'EC-01')
    expect(read.status).toBe(200)
    const create = await venueRequest('POST', '/venues', 'EC-01', newVenuePayload('Coordinator Write'))
    expect(create.status).toBe(403)
    const update = await venueRequest('PATCH', '/venues/v1', 'TS-01', { description: 'nope' })
    expect(update.status).toBe(403)
    const retire = await venueRequest('POST', '/venues/v2/retire', 'EO-01')
    expect(retire.status).toBe(403)
  })

  test('TC-SPM60-AC08 installing the system seeds the published catalogue', async () => {
    const list = await venueRequest('GET', '/venues', 'VS-01')
    const names = list.body.map((row) => row.name)
    expect(names).toEqual(
      expect.arrayContaining([
        'Marina Hall A',
        'Riverside Room 204',
        'Exhibition Hall B',
        'Skyline Boardroom',
      ]),
    )
  })

  test('TC-SPM60-AC09 every change is written to the activity log', async () => {
    const created = await venueRequest('POST', '/venues', 'VS-01', newVenuePayload('Logged Venue'))
    expect(created.status).toBe(201)
    await venueRequest('PATCH', `/venues/${created.body.venueId}`, 'VS-01', {
      description: 'logged edit',
    })
    const log = await venueRequest('GET', `/venues/${created.body.venueId}/activity-log`, 'VS-01')
    expect(log.status).toBe(200)
    const actions = log.body.map((row) => row.action)
    expect(actions).toEqual(expect.arrayContaining(['created', 'updated']))
    expect(log.body[0].changedBy).toBe('u3')
  })
})
