import { test, expect } from '@playwright/test'
import { equipmentPeriod } from './support/api-data.js'
import {
  checkAvailability,
  createEquipment,
  equipmentApi,
  planningEventWithRequest,
  reserveQuantity,
} from './support/equipment.js'

async function isolatedRequest(label, extras = {}) {
  const stock = await createEquipment(label, { totalQuantity: extras.totalQuantity ?? 5 })
  const setup = await planningEventWithRequest(label, {
    equipmentId: stock.equipmentId,
    quantity: extras.quantity ?? 2,
    sequence: extras.sequence ?? 330,
    window: extras.window,
  })
  return { stock, ...setup }
}

function lineFor(check, equipmentId) {
  const lines = check.body.lines || check.body
  return (Array.isArray(lines) ? lines : []).find((row) => row.equipmentId === equipmentId)
}

test.describe('SPM-02 Check equipment availability', () => {
  test('TC-SPM02-AC01 the check reports requested and available quantity for each line', async () => {
    const { event, stock } = await isolatedRequest('AUTO-SPM02-AC01', { quantity: 2, totalQuantity: 5 })
    const check = await checkAvailability(event.eventId)
    expect(check.status).toBe(200)
    const line = lineFor(check, stock.equipmentId)
    expect(line.requestedQuantity || line.quantityRequested).toBe(2)
    expect(line.availableQuantity).toBe(5)
  })

  test('TC-SPM02-AC02 available quantity excludes overlapping reservations', async () => {
    const stock = await createEquipment('AUTO-SPM02-AC02', { totalQuantity: 4 })
    const window = equipmentPeriod(331)
    const holder = await planningEventWithRequest('AUTO-SPM02-holder', {
      equipmentId: stock.equipmentId,
      quantity: 2,
      window,
    })
    const reserved = await reserveQuantity(holder.event.eventId, stock.equipmentId, 2, window)
    expect(reserved.status).toBe(201)

    const other = await planningEventWithRequest('AUTO-SPM02-other', {
      equipmentId: stock.equipmentId,
      quantity: 3,
      window,
    })
    const check = await checkAvailability(other.event.eventId)
    expect(check.status).toBe(200)
    expect(lineFor(check, stock.equipmentId).availableQuantity).toBe(2)
  })

  test('TC-SPM02-AC03 available quantity excludes damaged, maintenance, and retired units', async () => {
    const stock = await createEquipment('AUTO-SPM02-AC03', { totalQuantity: 6 })
    const oos = await equipmentApi('PATCH', `/equipment/${stock.equipmentId}`, 'TS-01', {
      outOfService: { damaged: 1, maintenance: 1, retired: 1 },
    })
    expect(oos.status).toBe(200)
    const setup = await planningEventWithRequest('AUTO-SPM02-oos', {
      equipmentId: stock.equipmentId,
      quantity: 2,
      sequence: 332,
    })
    const check = await checkAvailability(setup.event.eventId)
    expect(check.status).toBe(200)
    expect(lineFor(check, stock.equipmentId).availableQuantity).toBe(3)
  })

  test('TC-SPM02-AC04 the check states whether the request can be met and names each shortfall', async () => {
    const stock = await createEquipment('AUTO-SPM02-AC04', { totalQuantity: 2 })
    const setup = await planningEventWithRequest('AUTO-SPM02-short', {
      equipmentId: stock.equipmentId,
      quantity: 4,
      sequence: 333,
    })
    const check = await checkAvailability(setup.event.eventId)
    expect(check.status).toBe(200)
    expect(check.body.canMeet || check.body.canBeMet).toBe(false)
    const line = lineFor(check, stock.equipmentId)
    expect(line.shortfall).toBe(2)
    expect(JSON.stringify(check.body)).toMatch(new RegExp(stock.name || stock.equipmentId))
  })

  test('TC-SPM02-AC05 a shortfall names the overlapping events that hold the units', async () => {
    const stock = await createEquipment('AUTO-SPM02-AC05', { totalQuantity: 3 })
    const window = equipmentPeriod(334)
    const holder = await planningEventWithRequest('AUTO-SPM02-conflict', {
      equipmentId: stock.equipmentId,
      quantity: 3,
      window,
    })
    expect((await reserveQuantity(holder.event.eventId, stock.equipmentId, 3, window)).status).toBe(201)

    const other = await planningEventWithRequest('AUTO-SPM02-needs', {
      equipmentId: stock.equipmentId,
      quantity: 2,
      window,
    })
    const check = await checkAvailability(other.event.eventId)
    expect(check.status).toBe(200)
    const line = lineFor(check, stock.equipmentId)
    const conflicts = line.conflictingEvents || line.overlappingEvents || []
    expect(JSON.stringify(conflicts)).toMatch(new RegExp(holder.event.eventId))
  })

  test('TC-SPM02-AC06 periods that merely touch do not compete', async () => {
    const stock = await createEquipment('AUTO-SPM02-AC06', { totalQuantity: 4 })
    const first = equipmentPeriod(335, 2)
    const second = {
      startsAt: first.endsAt,
      endsAt: new Date(new Date(first.endsAt).getTime() + 2 * 60 * 60 * 1000).toISOString(),
    }
    const holder = await planningEventWithRequest('AUTO-SPM02-touch-a', {
      equipmentId: stock.equipmentId,
      quantity: 4,
      window: first,
    })
    expect((await reserveQuantity(holder.event.eventId, stock.equipmentId, 4, first)).status).toBe(201)

    const other = await planningEventWithRequest('AUTO-SPM02-touch-b', {
      equipmentId: stock.equipmentId,
      quantity: 4,
      window: second,
    })
    const check = await checkAvailability(other.event.eventId)
    expect(check.status).toBe(200)
    expect(lineFor(check, stock.equipmentId).availableQuantity).toBe(4)
  })

  test('TC-SPM02-AC07 re-running the check after a reserve or release reflects the new position', async () => {
    const stock = await createEquipment('AUTO-SPM02-AC07', { totalQuantity: 5 })
    const window = equipmentPeriod(336)
    const subject = await planningEventWithRequest('AUTO-SPM02-subject', {
      equipmentId: stock.equipmentId,
      quantity: 1,
      window,
    })
    const before = await checkAvailability(subject.event.eventId)
    expect(lineFor(before, stock.equipmentId).availableQuantity).toBe(5)

    const holder = await planningEventWithRequest('AUTO-SPM02-take', {
      equipmentId: stock.equipmentId,
      quantity: 2,
      window,
    })
    const reserved = await reserveQuantity(holder.event.eventId, stock.equipmentId, 2, window)
    expect(reserved.status).toBe(201)
    const afterReserve = await checkAvailability(subject.event.eventId)
    expect(lineFor(afterReserve, stock.equipmentId).availableQuantity).toBe(3)

    const released = await equipmentApi(
      'POST',
      `/equipment/reservations/${reserved.body.reservationId}/release`,
      'TS-01',
      { reason: 'AUTO-SPM02-release' },
    )
    expect([200, 204]).toContain(released.status)
    const afterRelease = await checkAvailability(subject.event.eventId)
    expect(lineFor(afterRelease, stock.equipmentId).availableQuantity).toBe(5)
  })

  test('TC-SPM02-AC08 the check never reserves anything and running it twice changes nothing', async () => {
    const { event, stock } = await isolatedRequest('AUTO-SPM02-AC08', { quantity: 1, sequence: 337 })
    const first = await checkAvailability(event.eventId)
    const second = await checkAvailability(event.eventId)
    expect(first.status).toBe(200)
    expect(second.status).toBe(200)
    expect(first.body).toEqual(second.body)
    const held = await equipmentApi('GET', `/equipment/${stock.equipmentId}/reservations`, 'TS-01')
    expect(held.status).toBe(200)
    const active = (held.body || []).filter((row) => /active|reserved/i.test(row.status))
    expect(active.length).toBe(0)
  })

  test('TC-SPM02-AC09 exact sufficiency, shortfall of one, overlap, out-of-service, and touching periods', async () => {
    const exactStock = await createEquipment('AUTO-SPM02-exact', { totalQuantity: 3 })
    const exact = await planningEventWithRequest('AUTO-SPM02-exact-event', {
      equipmentId: exactStock.equipmentId,
      quantity: 3,
      sequence: 338,
    })
    const exactCheck = await checkAvailability(exact.event.eventId)
    expect(exactCheck.body.canMeet || exactCheck.body.canBeMet).toBe(true)
    expect(lineFor(exactCheck, exactStock.equipmentId).availableQuantity).toBe(3)

    const shortStock = await createEquipment('AUTO-SPM02-by-one', { totalQuantity: 2 })
    const short = await planningEventWithRequest('AUTO-SPM02-by-one-event', {
      equipmentId: shortStock.equipmentId,
      quantity: 3,
      sequence: 339,
    })
    const shortCheck = await checkAvailability(short.event.eventId)
    expect(lineFor(shortCheck, shortStock.equipmentId).shortfall).toBe(1)

    const overlapStock = await createEquipment('AUTO-SPM02-overlap', { totalQuantity: 4 })
    const overlapWindow = equipmentPeriod(340)
    const overlapHolder = await planningEventWithRequest('AUTO-SPM02-overlap-a', {
      equipmentId: overlapStock.equipmentId,
      quantity: 1,
      window: overlapWindow,
    })
    expect(
      (await reserveQuantity(overlapHolder.event.eventId, overlapStock.equipmentId, 1, overlapWindow))
        .status,
    ).toBe(201)
    const overlapOther = await planningEventWithRequest('AUTO-SPM02-overlap-b', {
      equipmentId: overlapStock.equipmentId,
      quantity: 1,
      window: overlapWindow,
    })
    expect(lineFor(await checkAvailability(overlapOther.event.eventId), overlapStock.equipmentId).availableQuantity).toBe(3)

    const oosStock = await createEquipment('AUTO-SPM02-oos-matrix', { totalQuantity: 4 })
    await equipmentApi('PATCH', `/equipment/${oosStock.equipmentId}`, 'TS-01', {
      outOfService: { damaged: 1, maintenance: 0, retired: 0 },
    })
    const oosEvent = await planningEventWithRequest('AUTO-SPM02-oos-event', {
      equipmentId: oosStock.equipmentId,
      quantity: 1,
      sequence: 341,
    })
    expect(lineFor(await checkAvailability(oosEvent.event.eventId), oosStock.equipmentId).availableQuantity).toBe(3)

    const touchStock = await createEquipment('AUTO-SPM02-touch-matrix', { totalQuantity: 2 })
    const first = equipmentPeriod(342, 2)
    const second = {
      startsAt: first.endsAt,
      endsAt: new Date(new Date(first.endsAt).getTime() + 2 * 60 * 60 * 1000).toISOString(),
    }
    const touchHolder = await planningEventWithRequest('AUTO-SPM02-touch-hold', {
      equipmentId: touchStock.equipmentId,
      quantity: 2,
      window: first,
    })
    expect((await reserveQuantity(touchHolder.event.eventId, touchStock.equipmentId, 2, first)).status).toBe(201)
    const touchOther = await planningEventWithRequest('AUTO-SPM02-touch-next', {
      equipmentId: touchStock.equipmentId,
      quantity: 2,
      window: second,
    })
    expect(lineFor(await checkAvailability(touchOther.event.eventId), touchStock.equipmentId).availableQuantity).toBe(2)
  })
})
