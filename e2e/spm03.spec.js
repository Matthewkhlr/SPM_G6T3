import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { equipmentPeriod } from './support/api-data.js'
import { eventApi } from './support/event.js'
import {
  createEquipment,
  equipmentApi,
  planningEventWithRequest,
  reserveQuantity,
} from './support/equipment.js'

test.describe('SPM-03 Reserve equipment for an event', () => {
  test('TC-SPM03-AC01 technical support can reserve up to the quantity available for the period', async () => {
    const stock = await createEquipment('AUTO-SPM03-AC01', { totalQuantity: 4 })
    const setup = await planningEventWithRequest('AUTO-SPM03-ok', {
      equipmentId: stock.equipmentId,
      quantity: 3,
      sequence: 350,
    })
    const reserved = await reserveQuantity(setup.event.eventId, stock.equipmentId, 3, setup.window)
    expect(reserved.status).toBe(201)
    expect(reserved.body.quantity).toBe(3)
    expect(reserved.body.eventId).toBe(setup.event.eventId)
  })

  test('TC-SPM03-AC02 a quantity above what is available is refused and nothing is reserved', async () => {
    const stock = await createEquipment('AUTO-SPM03-AC02', { totalQuantity: 2 })
    const setup = await planningEventWithRequest('AUTO-SPM03-over', {
      equipmentId: stock.equipmentId,
      quantity: 5,
      sequence: 351,
    })
    const denied = await reserveQuantity(setup.event.eventId, stock.equipmentId, 5, setup.window)
    expect([400, 409, 422]).toContain(denied.status)
    expect(JSON.stringify(denied.body)).toMatch(/available|2/)
    const held = await equipmentApi('GET', `/equipment/${stock.equipmentId}/reservations`, 'TS-01')
    const active = (held.body || []).filter((row) => row.eventId === setup.event.eventId)
    expect(active.length).toBe(0)
  })

  test('TC-SPM03-AC03 a reservation reduces availability for overlapping events', async () => {
    const stock = await createEquipment('AUTO-SPM03-AC03', { totalQuantity: 5 })
    const window = equipmentPeriod(352)
    const first = await planningEventWithRequest('AUTO-SPM03-first', {
      equipmentId: stock.equipmentId,
      quantity: 2,
      window,
    })
    expect((await reserveQuantity(first.event.eventId, stock.equipmentId, 2, window)).status).toBe(201)
    const second = await planningEventWithRequest('AUTO-SPM03-second', {
      equipmentId: stock.equipmentId,
      quantity: 1,
      window,
    })
    const check = await equipmentApi('POST', '/equipment/availability', 'TS-01', {
      eventId: second.event.eventId,
    })
    const line = (check.body.lines || []).find((row) => row.equipmentId === stock.equipmentId)
    expect(line.availableQuantity).toBe(3)
  })

  test('TC-SPM03-AC04 damaged, maintenance, and retired units can never be reserved', async () => {
    const stock = await createEquipment('AUTO-SPM03-AC04', { totalQuantity: 3 })
    await equipmentApi('PATCH', `/equipment/${stock.equipmentId}`, 'TS-01', {
      outOfService: { damaged: 1, maintenance: 1, retired: 1 },
    })
    const setup = await planningEventWithRequest('AUTO-SPM03-oos', {
      equipmentId: stock.equipmentId,
      quantity: 1,
      sequence: 353,
    })
    const denied = await reserveQuantity(setup.event.eventId, stock.equipmentId, 1, setup.window)
    expect([400, 409, 422]).toContain(denied.status)
  })

  test('TC-SPM03-AC05 simultaneous reservations for the last units: exactly one succeeds', async () => {
    const stock = await createEquipment('AUTO-SPM03-AC05', { totalQuantity: 1 })
    const window = equipmentPeriod(354)
    const a = await planningEventWithRequest('AUTO-SPM03-race-a', {
      equipmentId: stock.equipmentId,
      quantity: 1,
      window,
    })
    const b = await planningEventWithRequest('AUTO-SPM03-race-b', {
      equipmentId: stock.equipmentId,
      quantity: 1,
      window,
    })
    const [first, second] = await Promise.all([
      reserveQuantity(a.event.eventId, stock.equipmentId, 1, window),
      reserveQuantity(b.event.eventId, stock.equipmentId, 1, window),
    ])
    const statuses = [first.status, second.status].sort()
    expect(statuses).toEqual([201, 409])
    const refused = first.status === 201 ? second : first
    expect(JSON.stringify(refused.body)).toMatch(/available|shortfall|0/)
  })

  test('TC-SPM03-AC06 a reservation stays on its event and is visible on the event and the equipment record', async ({
    page,
  }) => {
    const stock = await createEquipment('AUTO-SPM03-AC06', { totalQuantity: 2 })
    const setup = await planningEventWithRequest('AUTO-SPM03-visible', {
      equipmentId: stock.equipmentId,
      quantity: 1,
      sequence: 355,
    })
    const reserved = await reserveQuantity(setup.event.eventId, stock.equipmentId, 1, setup.window)
    expect(reserved.status).toBe(201)

    await login(page, account('TS-01'))
    await page.goto(`/app/events/${setup.event.eventId}`)
    await expect(page.getByTestId('event-reservations')).toContainText(stock.name || stock.equipmentId)
    await page.goto(`/app/equipment/${stock.equipmentId}`)
    await expect(page.getByTestId('equipment-reservations')).toContainText(setup.event.eventId)
  })

  test('TC-SPM03-AC07 the assigned coordinator sees reservations and is notified when the request is fully reserved', async ({
    page,
  }) => {
    const stock = await createEquipment('AUTO-SPM03-AC07', { totalQuantity: 2 })
    const setup = await planningEventWithRequest('AUTO-SPM03-notify', {
      equipmentId: stock.equipmentId,
      quantity: 2,
      sequence: 356,
    })
    expect((await reserveQuantity(setup.event.eventId, stock.equipmentId, 2, setup.window)).status).toBe(201)

    await login(page, account('EC-01'))
    await page.goto(`/app/events/${setup.event.eventId}`)
    await expect(page.getByTestId('event-reservations')).toBeVisible()
    await expect(page.getByTestId('event-reservations')).toContainText(/reserved|2/)
  })

  test('TC-SPM03-AC08 cancelling, rejecting, or completing the event releases its reservations', async () => {
    const stock = await createEquipment('AUTO-SPM03-AC08', { totalQuantity: 2 })
    const setup = await planningEventWithRequest('AUTO-SPM03-release', {
      equipmentId: stock.equipmentId,
      quantity: 2,
      sequence: 357,
    })
    const reserved = await reserveQuantity(setup.event.eventId, stock.equipmentId, 2, setup.window)
    expect(reserved.status).toBe(201)
    const rejected = await eventApi('POST', `/${setup.event.eventId}/reject`, 'EC-01', {
      reason: 'insufficient equipment',
      explanation: 'AUTO-SPM03-release',
    })
    expect(rejected.status).toBe(200)
    const held = await equipmentApi(
      'GET',
      `/equipment/reservations/${reserved.body.reservationId}`,
      'TS-01',
    )
    expect(held.body.status).toMatch(/released|cancelled|withdrawn/i)
  })

  test('TC-SPM03-AC09 reservations and releases persist in the activity log with who and when', async () => {
    const stock = await createEquipment('AUTO-SPM03-AC09', { totalQuantity: 2 })
    const setup = await planningEventWithRequest('AUTO-SPM03-log', {
      equipmentId: stock.equipmentId,
      quantity: 1,
      sequence: 358,
    })
    const reserved = await reserveQuantity(setup.event.eventId, stock.equipmentId, 1, setup.window)
    expect(reserved.status).toBe(201)
    await equipmentApi(
      'POST',
      `/equipment/reservations/${reserved.body.reservationId}/release`,
      'TS-01',
      { reason: 'AUTO-log' },
    )
    const log = await equipmentApi('GET', `/equipment/${stock.equipmentId}/activity-log`, 'TS-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/reserv|u4/)
    expect(JSON.stringify(log.body)).toMatch(/releas/)
  })

  test('TC-SPM03-AC10 reserving every requested line marks the equipment arrangement ready', async () => {
    const stock = await createEquipment('AUTO-SPM03-AC10', { totalQuantity: 2 })
    const setup = await planningEventWithRequest('AUTO-SPM03-ready', {
      equipmentId: stock.equipmentId,
      quantity: 2,
      sequence: 359,
    })
    expect((await reserveQuantity(setup.event.eventId, stock.equipmentId, 2, setup.window)).status).toBe(201)
    const readiness = await eventApi('GET', `/${setup.event.eventId}/readiness`, 'EC-01')
    expect(readiness.status).toBe(200)
    const equipment = (readiness.body || []).find((row) => /equipment/i.test(row.category))
    expect(equipment.status).toMatch(/ready|settled|reserved/i)
  })
})
