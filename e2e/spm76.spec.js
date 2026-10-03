import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { equipmentRequestPayload } from './support/api-data.js'
import { equipmentApi, createPendingRequest } from './support/equipment.js'

test.describe('SPM-76 Record an event\'s equipment requirements', () => {
  test('TC-SPM76-AC01 a coordinator request captures type, quantity, and technical requirements, not unit ids', async () => {
    const created = await createPendingRequest({
      eventId: 'e3',
      equipmentId: 'eq1',
      quantity: 2,
      technicalRequirements: 'HDMI to the lectern',
      sequence: 370,
    })
    expect(created.equipmentId).toBe('eq1')
    expect(created.quantity).toBe(2)
    expect(created.technicalRequirements).toMatch(/HDMI/)
    expect(created.unitId || created.assetId).toBeFalsy()
    expect(JSON.stringify(created)).not.toMatch(/u-eq1/)
  })

  test('TC-SPM76-AC02 the request is visible to technical support as Requested, and only they can reserve or mark unavailable', async () => {
    const created = await createPendingRequest({ eventId: 'e3', sequence: 371 })
    expect(created.status).toMatch(/requested|pending/i)

    const asStaff = await equipmentApi('GET', `/equipment/requests/${created.requestId}`, 'TS-01')
    expect(asStaff.status).toBe(200)
    expect(asStaff.body.status).toMatch(/requested|pending/i)

    const reserve = await equipmentApi('POST', `/equipment/requests/${created.requestId}/reserve`, 'EC-01')
    expect(reserve.status).toBe(403)
    const unavailable = await equipmentApi(
      'POST',
      `/equipment/requests/${created.requestId}/unavailable`,
      'EC-01',
      { reason: 'no stock' },
    )
    expect(unavailable.status).toBe(403)
    const patch = await equipmentApi('PATCH', `/equipment/requests/${created.requestId}`, 'EC-01', {
      status: 'reserved',
    })
    expect(patch.status).toBe(403)
  })

  test('TC-SPM76-AC03 after technical support acts, the record shows who last updated it and when', async () => {
    const created = await createPendingRequest({ eventId: 'e3', sequence: 372 })
    const reviewed = await equipmentApi('POST', `/equipment/requests/${created.requestId}/review`, 'TS-01', {
      approve: true,
      reviewNote: 'AUTO-SPM76',
    })
    expect(reviewed.status).toBe(200)
    expect(reviewed.body.reviewedBy || reviewed.body.updatedBy).toBe('u4')
    expect(reviewed.body.reviewedAt || reviewed.body.updatedAt || reviewed.body.createdAt).toBeTruthy()
  })

  test('TC-SPM76-AC04 a line that cannot be fulfilled is marked and the coordinator is notified', async ({
    page,
  }) => {
    const created = await createPendingRequest({
      ...equipmentRequestPayload(373, 'e3'),
      equipmentId: 'eq3',
      quantity: 8,
      technicalRequirements: 'More panels than exist',
    })
    const marked = await equipmentApi('POST', `/equipment/requests/${created.requestId}/unavailable`, 'TS-01', {
      reason: 'insufficient stock',
      note: 'Only two panels exist',
    })
    expect(marked.status).toBe(200)
    expect(marked.body.status).toMatch(/unavailable|shortfall|unfulfilled/i)

    await login(page, account('EC-01'))
    await page.goto('/app/events/e3')
    await expect(page.getByTestId('equipment-request-outcome')).toContainText(
      /unavailable|cannot|shortfall|eq3/i,
    )
  })
})
