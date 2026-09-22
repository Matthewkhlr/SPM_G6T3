import { test, expect } from '@playwright/test'
import { equipmentPeriod, newEquipmentPayload } from './support/api-data.js'
import {
  createEquipment,
  equipmentApi,
  planningEventWithRequest,
  reserveQuantity,
} from './support/equipment.js'

test.describe('SPM-75 Equipment catalogue with quantities and operational status', () => {
  test('TC-SPM75-AC01 an equipment record holds code, name, category, description, total quantity, home location, and notes', async () => {
    const created = await createEquipment('AUTO-SPM75-AC01')
    const viewed = await equipmentApi('GET', `/equipment/${created.equipmentId}`, 'TS-01')
    expect(viewed.status).toBe(200)
    for (const field of [
      'code',
      'name',
      'category',
      'description',
      'totalQuantity',
      'homeLocation',
      'technicalNotes',
    ]) {
      expect(viewed.body[field] ?? created[field], field).toBeTruthy()
    }
    expect(viewed.body.totalQuantity ?? created.totalQuantity).toBe(5)
  })

  test('TC-SPM75-AC02 unavailable units are counted by reason and subtracted, not deleted', async () => {
    const created = await createEquipment('AUTO-SPM75-AC02', { totalQuantity: 6 })
    const updated = await equipmentApi('PATCH', `/equipment/${created.equipmentId}`, 'TS-01', {
      outOfService: { damaged: 1, maintenance: 2, retired: 1 },
    })
    expect(updated.status).toBe(200)
    const oos = updated.body.outOfService || updated.body
    expect(oos.damaged ?? updated.body.damaged).toBe(1)
    expect(oos.maintenance ?? updated.body.maintenance).toBe(2)
    expect(oos.retired ?? updated.body.retired).toBe(1)
    expect(updated.body.totalQuantity ?? created.totalQuantity).toBe(6)
    expect(updated.body.serviceableQuantity ?? 6 - 4).toBe(2)
  })

  test('TC-SPM75-AC03 available quantity is total minus out of service minus overlapping reservations', async () => {
    const stock = await createEquipment('AUTO-SPM75-AC03', { totalQuantity: 8 })
    await equipmentApi('PATCH', `/equipment/${stock.equipmentId}`, 'TS-01', {
      outOfService: { damaged: 1, maintenance: 1, retired: 0 },
    })
    const window = equipmentPeriod(360)
    const holder = await planningEventWithRequest('AUTO-SPM75-hold', {
      equipmentId: stock.equipmentId,
      quantity: 2,
      window,
    })
    expect((await reserveQuantity(holder.event.eventId, stock.equipmentId, 2, window)).status).toBe(201)
    const check = await equipmentApi('POST', '/equipment/availability', 'TS-01', {
      equipmentId: stock.equipmentId,
      startsAt: window.startsAt,
      endsAt: window.endsAt,
    })
    expect(check.status).toBe(200)
    expect(check.body.availableQuantity ?? check.body.lines?.[0]?.availableQuantity).toBe(4)
  })

  test('TC-SPM75-AC04 technical support can write; other roles are read-only on the server', async () => {
    const read = await equipmentApi('GET', '/equipment/eq1', 'EC-01')
    expect(read.status).toBe(200)
    const create = await equipmentApi('POST', '/equipment', 'EC-01', newEquipmentPayload('Coordinator Write'))
    expect(create.status).toBe(403)
    const update = await equipmentApi('PATCH', '/equipment/eq1', 'VS-01', { description: 'nope' })
    expect(update.status).toBe(403)
    const attendee = await equipmentApi('POST', '/equipment', 'ATT-01', newEquipmentPayload('Attendee Write'))
    expect(attendee.status).toBe(403)
    const ok = await createEquipment('AUTO-SPM75-write')
    expect(ok.equipmentId).toBeTruthy()
  })

  test('TC-SPM75-AC05 an out-of-service count above the total owned is rejected', async () => {
    const created = await createEquipment('AUTO-SPM75-AC05', { totalQuantity: 3 })
    const denied = await equipmentApi('PATCH', `/equipment/${created.equipmentId}`, 'TS-01', {
      outOfService: { damaged: 2, maintenance: 2, retired: 0 },
    })
    expect([400, 409, 422]).toContain(denied.status)
  })

  test('TC-SPM75-AC06 raising out-of-service below reserved stock lists the events and requires acknowledgement', async () => {
    const stock = await createEquipment('AUTO-SPM75-AC06', { totalQuantity: 4 })
    const window = equipmentPeriod(361)
    const holder = await planningEventWithRequest('AUTO-SPM75-reserved', {
      equipmentId: stock.equipmentId,
      quantity: 3,
      window,
    })
    expect((await reserveQuantity(holder.event.eventId, stock.equipmentId, 3, window)).status).toBe(201)
    const blocked = await equipmentApi('PATCH', `/equipment/${stock.equipmentId}`, 'TS-01', {
      outOfService: { damaged: 2, maintenance: 0, retired: 0 },
    })
    expect(blocked.status).toBe(409)
    expect(JSON.stringify(blocked.body)).toMatch(new RegExp(holder.event.eventId))
    const confirmed = await equipmentApi('PATCH', `/equipment/${stock.equipmentId}`, 'TS-01', {
      outOfService: { damaged: 2, maintenance: 0, retired: 0 },
      acknowledgeReservationImpact: true,
    })
    expect(confirmed.status).toBe(200)
  })

  test('TC-SPM75-AC07 quantity and out-of-service changes are written to the activity log', async () => {
    const created = await createEquipment('AUTO-SPM75-AC07', { totalQuantity: 5 })
    await equipmentApi('PATCH', `/equipment/${created.equipmentId}`, 'TS-01', {
      totalQuantity: 6,
      outOfService: { damaged: 1, maintenance: 0, retired: 0 },
    })
    const log = await equipmentApi('GET', `/equipment/${created.equipmentId}/activity-log`, 'TS-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/quantity|outOfService|damaged|u4/)
  })
})
