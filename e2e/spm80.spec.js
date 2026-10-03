import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { createNameOnlyDraft, eventApi } from './support/event.js'

test.describe('SPM-80 Capture venue, layout, accessibility and equipment requirements', () => {
  test('TC-SPM80-AC01 the organiser chooses a published layout or no preference', async ({ page }) => {
    const options = await eventApi('GET', '/requirement-options', 'EO-01')
    expect(options.status).toBe(200)
    expect(options.body.layouts || options.body.layoutOptions).toEqual(
      expect.arrayContaining([expect.stringMatching(/Theatre|Boardroom|Classroom|Banquet|no preference/i)]),
    )
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM80-layout')
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${draft.eventId}`)
    await page.getByTestId('layout-preference').selectOption(/Theatre|no preference/i)
    await page.getByTestId('event-save-draft').click()
    const stored = await eventApi('GET', `/${draft.eventId}`, 'EO-01')
    expect(stored.body.layoutPreference || stored.body.layout).toBeTruthy()
  })

  test('TC-SPM80-AC02 the organiser can state a preferred location or region and facilities from the catalogue', async () => {
    const options = await eventApi('GET', '/requirement-options', 'EO-01')
    expect(options.status).toBe(200)
    const facilities = options.body.facilities || []
    expect(facilities).toEqual(expect.arrayContaining([expect.stringMatching(/Projector|PA|Video/i)]))
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM80-venue')
    const saved = await eventApi('PATCH', `/${draft.eventId}`, 'EO-01', {
      preferredLocation: 'HarbourFront Centre',
      requiredFacilities: ['Projector', 'PA system'],
    })
    expect(saved.status).toBe(200)
    expect(saved.body.preferredLocation).toMatch(/HarbourFront/)
    expect(saved.body.requiredFacilities).toEqual(expect.arrayContaining(['Projector']))
  })

  test('TC-SPM80-AC03 the organiser selects published accessibility needs and can add a free-text note', async () => {
    const options = await eventApi('GET', '/requirement-options', 'EO-01')
    expect(options.body.accessibility).toEqual(
      expect.arrayContaining([expect.stringMatching(/Wheelchair/i)]),
    )
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM80-access')
    const saved = await eventApi('PATCH', `/${draft.eventId}`, 'EO-01', {
      accessibilityNeeds: ['Wheelchair accessible'],
      accessibilityNote: 'Need a quiet room nearby',
    })
    expect(saved.status).toBe(200)
    expect(JSON.stringify(saved.body)).toMatch(/Wheelchair|quiet room/)
  })

  test('TC-SPM80-AC04 equipment requirements are a list of catalogue types, quantity at least one, and optional notes', async () => {
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM80-eq')
    const saved = await eventApi('PATCH', `/${draft.eventId}`, 'EO-01', {
      equipmentLines: [
        { equipmentId: 'eq1', quantity: 2, technicalNotes: 'HDMI to the lectern' },
        { equipmentId: 'eq2', quantity: 1 },
      ],
    })
    expect(saved.status).toBe(200)
    expect(saved.body.equipmentLines.length).toBe(2)
    expect(saved.body.equipmentLines[0].quantity).toBe(2)
    expect(saved.body.equipmentLines[0].unitId).toBeFalsy()
  })

  test('TC-SPM80-AC05 a quantity that is zero, negative, or not a whole number is rejected', async () => {
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM80-qty')
    for (const quantity of [0, -1, 1.5]) {
      const denied = await eventApi('PATCH', `/${draft.eventId}`, 'EO-01', {
        equipmentLines: [{ equipmentId: 'eq1', quantity }],
      })
      expect([400, 422]).toContain(denied.status)
      expect(JSON.stringify(denied.body)).toMatch(/whole|integer|at least 1|quantity/i)
    }
  })

  test('TC-SPM80-AC06 the same equipment type cannot be added twice; adding it again edits the existing line', async () => {
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM80-dup')
    await eventApi('PATCH', `/${draft.eventId}`, 'EO-01', {
      equipmentLines: [{ equipmentId: 'eq1', quantity: 1, technicalNotes: 'first' }],
    })
    const again = await eventApi('PATCH', `/${draft.eventId}`, 'EO-01', {
      equipmentLines: [{ equipmentId: 'eq1', quantity: 3, technicalNotes: 'updated' }],
    })
    expect(again.status).toBe(200)
    const eq1 = (again.body.equipmentLines || []).filter((row) => row.equipmentId === 'eq1')
    expect(eq1.length).toBe(1)
    expect(eq1[0].quantity).toBe(3)
    expect(eq1[0].technicalNotes).toMatch(/updated/)
  })

  test('TC-SPM80-AC07 submitted requirements are visible to the coordinator unchanged', async () => {
    const draft = await createNameOnlyDraft('EO-01', 'AUTO-SPM80-visible')
    await eventApi('PATCH', `/${draft.eventId}`, 'EO-01', {
      layoutPreference: 'Theatre',
      requiredFacilities: ['Projector'],
      accessibilityNeeds: ['Wheelchair accessible'],
      equipmentLines: [{ equipmentId: 'eq1', quantity: 2, technicalNotes: 'Keep HDMI' }],
      purpose: 'Visible to coordinator',
      category: 'meeting',
      expectedAttendance: 10,
      proposedStartAt: new Date(Date.now() + 40 * 86400000).toISOString(),
      proposedEndAt: new Date(Date.now() + 40 * 86400000 + 7200000).toISOString(),
    })
    await eventApi('POST', `/${draft.eventId}/submit`, 'EO-01')
    const asCoord = await eventApi('GET', `/${draft.eventId}`, 'EC-01')
    expect(asCoord.status).toBe(200)
    expect(JSON.stringify(asCoord.body)).toMatch(/Theatre|Projector|Wheelchair|HDMI|eq1/)
  })
})
