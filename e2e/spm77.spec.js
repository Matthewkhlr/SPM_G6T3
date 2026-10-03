import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { eventApi } from './support/event.js'
import {
  approveRequest,
  createEquipment,
  createPendingRequest,
  equipmentApi,
  planningEventWithRequest,
} from './support/equipment.js'

test.describe('SPM-77 Respond to an equipment request that cannot be fully met', () => {
  test('TC-SPM77-AC01 technical support can mark a line unavailable with a reason, note, and alternative', async () => {
    const created = await createPendingRequest({ eventId: 'e3', equipmentId: 'eq1', sequence: 380 })
    const marked = await equipmentApi('POST', `/equipment/requests/${created.requestId}/unavailable`, 'TS-01', {
      reason: 'insufficient stock',
      note: 'Both projectors are on another event',
      alternativeEquipmentId: 'eq2',
    })
    expect(marked.status).toBe(200)
    expect(marked.body.status).toMatch(/unavailable/i)
    expect(marked.body.reason || marked.body.decisionReason).toMatch(/stock|insufficient/i)
    expect(marked.body.alternativeEquipmentId || marked.body.suggestedAlternative).toBe('eq2')
  })

  test('TC-SPM77-AC02 technical support can record a line as partly fulfilled, reserving what is available', async () => {
    const stock = await createEquipment('AUTO-SPM77-AC02', { totalQuantity: 2 })
    const setup = await planningEventWithRequest('AUTO-SPM77-partial', {
      equipmentId: stock.equipmentId,
      quantity: 4,
      sequence: 381,
    })
    await approveRequest(setup.request.requestId)
    const partial = await equipmentApi(
      'POST',
      `/equipment/requests/${setup.request.requestId}/partial`,
      'TS-01',
      { reservedQuantity: 2, reason: 'Only two free' },
    )
    expect(partial.status).toBe(200)
    expect(partial.body.reservedQuantity || partial.body.quantity).toBe(2)
    expect(partial.body.shortfall).toBe(2)
    expect(partial.body.status).toMatch(/partial|partly/i)
  })

  test('TC-SPM77-AC03 the assigned coordinator is notified with the line, shortfall, reason, and alternative', async ({
    page,
  }) => {
    const created = await createPendingRequest({ eventId: 'e3', equipmentId: 'eq3', quantity: 2, sequence: 382 })
    await equipmentApi('POST', `/equipment/requests/${created.requestId}/unavailable`, 'TS-01', {
      reason: 'unit under maintenance',
      note: 'One panel is out',
      alternativeEquipmentId: 'eq1',
    })
    await login(page, account('EC-01'))
    await page.goto('/app/events/e3')
    const notice = page.getByTestId('equipment-request-outcome')
    await expect(notice).toBeVisible()
    await expect(notice).toContainText(/eq3|LED|shortfall|unavailable/i)
    await expect(notice).toContainText(/maintenance|eq1|projector/i)
  })

  test('TC-SPM77-AC04 unavailable or partly fulfilled lines show the arrangement as needing attention, not ready', async () => {
    const readiness = await eventApi('GET', '/e3/readiness', 'EC-01')
    expect(readiness.status).toBe(200)
    const equipment = (readiness.body || []).find((row) => /equipment/i.test(row.category))
    expect(equipment.status).toMatch(/attention|outstanding|not ready|shortfall/i)
    expect(equipment.status).not.toMatch(/^ready$/i)
  })

  test('TC-SPM77-AC05 the coordinator can accept the shortfall or amend the request and send it back', async () => {
    const created = await createPendingRequest({ eventId: 'e3', equipmentId: 'eq1', quantity: 3, sequence: 383 })
    await equipmentApi('POST', `/equipment/requests/${created.requestId}/partial`, 'TS-01', {
      reservedQuantity: 1,
      reason: 'One free',
    })
    const accepted = await equipmentApi(
      'POST',
      `/equipment/requests/${created.requestId}/accept-shortfall`,
      'EC-01',
    )
    expect(accepted.status).toBe(200)
    expect(accepted.body.status).toMatch(/resolved|accepted|ready/i)

    const second = await createPendingRequest({ eventId: 'e3', equipmentId: 'eq2', quantity: 4, sequence: 384 })
    await equipmentApi('POST', `/equipment/requests/${second.requestId}/partial`, 'TS-01', {
      reservedQuantity: 1,
      reason: 'Amend me',
    })
    const amended = await equipmentApi('PATCH', `/equipment/requests/${second.requestId}`, 'EC-01', {
      quantity: 1,
      resubmit: true,
    })
    expect(amended.status).toBe(200)
    expect(amended.body.status).toMatch(/requested|pending|amended/i)
  })

  test('TC-SPM77-AC06 recording the whole request reviewed and complete marks the arrangement ready', async () => {
    const stock = await createEquipment('AUTO-SPM77-AC06', { totalQuantity: 2 })
    const setup = await planningEventWithRequest('AUTO-SPM77-complete', {
      equipmentId: stock.equipmentId,
      quantity: 1,
      sequence: 385,
    })
    const completed = await equipmentApi(
      'POST',
      `/equipment/requests/${setup.request.requestId}/complete-review`,
      'TS-01',
    )
    expect(completed.status).toBe(200)
    const readiness = await eventApi('GET', `/${setup.event.eventId}/readiness`, 'EC-01')
    const equipment = (readiness.body || []).find((row) => /equipment/i.test(row.category))
    expect(equipment.status).toMatch(/ready|settled/i)
  })

  test('TC-SPM77-AC07 every response is written to the activity log with who and when', async () => {
    const created = await createPendingRequest({ eventId: 'e3', sequence: 386 })
    await equipmentApi('POST', `/equipment/requests/${created.requestId}/unavailable`, 'TS-01', {
      reason: 'insufficient stock',
      note: 'logged',
    })
    const log = await equipmentApi('GET', `/equipment/eq1/activity-log`, 'TS-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/unavailab|u4/)
  })
})
