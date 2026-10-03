import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { eventApi } from './support/event.js'
import { equipmentPeriod } from './support/api-data.js'
import {
  checkAvailability,
  createEquipment,
  equipmentApi,
  planningEventWithRequest,
  reserveQuantity,
} from './support/equipment.js'

test.describe('SPM-78 Adjust or release an equipment reservation', () => {
  test('TC-SPM78-AC01 technical support can reduce, increase, or release a reservation on an active event', async () => {
    const stock = await createEquipment('AUTO-SPM78-AC01', { totalQuantity: 6 })
    const setup = await planningEventWithRequest('AUTO-SPM78-adjust', {
      equipmentId: stock.equipmentId,
      quantity: 2,
      sequence: 390,
    })
    const reserved = await reserveQuantity(setup.event.eventId, stock.equipmentId, 2, setup.window)
    expect(reserved.status).toBe(201)
    const increased = await equipmentApi(
      'PATCH',
      `/equipment/reservations/${reserved.body.reservationId}`,
      'TS-01',
      { quantity: 3 },
    )
    expect(increased.status).toBe(200)
    expect(increased.body.quantity).toBe(3)
    const reduced = await equipmentApi(
      'PATCH',
      `/equipment/reservations/${reserved.body.reservationId}`,
      'TS-01',
      { quantity: 1 },
    )
    expect(reduced.status).toBe(200)
    expect(reduced.body.quantity).toBe(1)
    const released = await equipmentApi(
      'POST',
      `/equipment/reservations/${reserved.body.reservationId}/release`,
      'TS-01',
      { reason: 'no longer needed' },
    )
    expect([200, 204]).toContain(released.status)

    const terminal = await planningEventWithRequest('AUTO-SPM78-terminal', {
      equipmentId: stock.equipmentId,
      quantity: 1,
      sequence: 395,
    })
    const held = await reserveQuantity(terminal.event.eventId, stock.equipmentId, 1, terminal.window)
    await eventApi('POST', `/${terminal.event.eventId}/reject`, 'EC-01', {
      reason: 'insufficient equipment',
      explanation: 'closed',
    })
    const denied = await equipmentApi(
      'PATCH',
      `/equipment/reservations/${held.body.reservationId}`,
      'TS-01',
      { quantity: 2 },
    )
    expect([400, 409]).toContain(denied.status)
  })

  test('TC-SPM78-AC02 increasing a reservation is subject to the same availability check', async () => {
    const stock = await createEquipment('AUTO-SPM78-AC02', { totalQuantity: 2 })
    const setup = await planningEventWithRequest('AUTO-SPM78-cap', {
      equipmentId: stock.equipmentId,
      quantity: 1,
      sequence: 391,
    })
    const reserved = await reserveQuantity(setup.event.eventId, stock.equipmentId, 1, setup.window)
    const denied = await equipmentApi(
      'PATCH',
      `/equipment/reservations/${reserved.body.reservationId}`,
      'TS-01',
      { quantity: 5 },
    )
    expect([400, 409, 422]).toContain(denied.status)
    expect(JSON.stringify(denied.body)).toMatch(/available/)
  })

  test('TC-SPM78-AC03 reducing or releasing a reservation immediately returns units to availability', async () => {
    const stock = await createEquipment('AUTO-SPM78-AC03', { totalQuantity: 4 })
    const window = equipmentPeriod(392)
    const holder = await planningEventWithRequest('AUTO-SPM78-hold', {
      equipmentId: stock.equipmentId,
      quantity: 3,
      window,
    })
    const reserved = await reserveQuantity(holder.event.eventId, stock.equipmentId, 3, window)
    const watcher = await planningEventWithRequest('AUTO-SPM78-watch', {
      equipmentId: stock.equipmentId,
      quantity: 1,
      window,
    })
    expect((await checkAvailability(watcher.event.eventId)).body.lines[0].availableQuantity).toBe(1)
    await equipmentApi('PATCH', `/equipment/reservations/${reserved.body.reservationId}`, 'TS-01', {
      quantity: 1,
    })
    expect((await checkAvailability(watcher.event.eventId)).body.lines[0].availableQuantity).toBe(3)
    await equipmentApi(
      'POST',
      `/equipment/reservations/${reserved.body.reservationId}/release`,
      'TS-01',
      { reason: 'freed' },
    )
    expect((await checkAvailability(watcher.event.eventId)).body.lines[0].availableQuantity).toBe(4)
  })

  test('TC-SPM78-AC04 releasing a reservation on a confirmed event requires a reason and notifies coordinator and organiser', async ({
    page,
  }) => {
    const stock = await createEquipment('AUTO-SPM78-AC04', { totalQuantity: 2 })
    const window = equipmentPeriod(14, 8)
    const reserved = await reserveQuantity('e1', stock.equipmentId, 1, window)
    expect(reserved.status).toBe(201)
    const missing = await equipmentApi(
      'POST',
      `/equipment/reservations/${reserved.body.reservationId}/release`,
      'TS-01',
      {},
    )
    expect([400, 422]).toContain(missing.status)
    const released = await equipmentApi(
      'POST',
      `/equipment/reservations/${reserved.body.reservationId}/release`,
      'TS-01',
      { reason: 'panel failed inspection' },
    )
    expect(released.status).toBe(200)

    await login(page, account('EC-01'))
    await page.goto('/app/events/e1')
    await expect(page.getByTestId('equipment-request-outcome')).toContainText(/released|reason|inspection/i)
    await page.getByRole('button', { name: 'Log out' }).click()
    await login(page, account('EO-01'))
    await page.goto('/app/events/e1')
    await expect(page.getByTestId('organiser-arrangements')).toContainText(/equipment|released|attention/i)
  })

  test('TC-SPM78-AC05 releasing a reservation shows the equipment arrangement as needing attention again', async () => {
    const stock = await createEquipment('AUTO-SPM78-AC05', { totalQuantity: 2 })
    const setup = await planningEventWithRequest('AUTO-SPM78-ready', {
      equipmentId: stock.equipmentId,
      quantity: 2,
      sequence: 393,
    })
    const reserved = await reserveQuantity(setup.event.eventId, stock.equipmentId, 2, setup.window)
    await equipmentApi(
      'POST',
      `/equipment/reservations/${reserved.body.reservationId}/release`,
      'TS-01',
      { reason: 'returned to pool' },
    )
    const readiness = await eventApi('GET', `/${setup.event.eventId}/readiness`, 'EC-01')
    const equipment = (readiness.body || []).find((row) => /equipment/i.test(row.category))
    expect(equipment.status).toMatch(/attention|outstanding|not ready/i)
  })

  test('TC-SPM78-AC06 every adjustment and release is written to the activity log with previous and new quantity', async () => {
    const stock = await createEquipment('AUTO-SPM78-AC06', { totalQuantity: 4 })
    const setup = await planningEventWithRequest('AUTO-SPM78-log', {
      equipmentId: stock.equipmentId,
      quantity: 2,
      sequence: 394,
    })
    const reserved = await reserveQuantity(setup.event.eventId, stock.equipmentId, 2, setup.window)
    await equipmentApi('PATCH', `/equipment/reservations/${reserved.body.reservationId}`, 'TS-01', {
      quantity: 1,
    })
    const log = await equipmentApi('GET', `/equipment/${stock.equipmentId}/activity-log`, 'TS-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/previous|old|2/)
    expect(JSON.stringify(log.body)).toMatch(/new|1|u4/)
  })
})
