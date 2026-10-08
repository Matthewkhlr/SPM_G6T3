import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { equipmentApi } from './support/equipment.js'
import { notificationApi } from './support/registration.js'
import { venueRequest } from './support/venue.js'
import {
  bookVenue,
  confirm,
  confirmation,
  distantPeriod,
  events,
  passSafetyReview,
  planningEvent,
  planningEventWithEquipment,
  readyToConfirm,
} from './support/confirmation.js'

const DAY = 24 * 60 * 60 * 1000

async function inbox(accountId) {
  return JSON.stringify((await notificationApi('GET', '/notifications', accountId)).body)
}

test.describe('SPM-72 Confirm an event', () => {
  test('TC-SPM72-AC01 confirmation needs an approved venue booking for the event date and time, and every equipment line reserved or recorded as not required', async () => {
    const event = await planningEventWithEquipment('SPM72-ac01')
    const elsewhere = await bookVenue(event, distantPeriod())

    let check = await confirmation(event)
    expect(check.status, JSON.stringify(check.body)).toBe(200)
    expect(check.body.ready).toBe(false)
    const messages = check.body.missing.map((gap) => gap.message).join(' ')
    expect(messages).toContain("is not for the event's date and time")
    const line = check.body.missing.find((gap) => gap.equipmentId === 'eq1')
    expect(line.message).toMatch(/neither reserved nor recorded as not required/)

    const blank = await events('POST', `/${event.eventId}/equipment-lines/eq1/not-required`, 'EC-01', { reason: '  ' })
    expect(blank.status).toBe(422)
    const marked = await events('POST', `/${event.eventId}/equipment-lines/eq1/not-required`, 'EC-01', {
      reason: 'The venue has a built-in projector.',
    })
    expect(marked.status, JSON.stringify(marked.body)).toBe(200)
    expect(marked.body.equipmentLines[0]).toMatchObject({
      notRequired: true,
      notRequiredReason: 'The venue has a built-in projector.',
      notRequiredBy: 'u2',
    })

    // The booking left at another time does not count: cancel it and book the event's time.
    const cancelled = await venueRequest('POST', `/venues/bookings/${elsewhere.bookingId}/cancel`, 'EC-01')
    expect(cancelled.status, JSON.stringify(cancelled.body)).toBe(200)
    await bookVenue(event)
    check = await confirmation(event)
    expect(check.body.missing.map((gap) => gap.kind)).toEqual(['safety'])

    await passSafetyReview(event)
    check = await confirmation(event)
    expect(check.body).toMatchObject({ ready: true, missing: [] })
  })

  test('TC-SPM72-AC02 confirm is unavailable while an arrangement is outstanding and the view names what is missing', async ({
    page,
  }) => {
    const event = await planningEventWithEquipment('SPM72-ac02')
    const refused = await confirm(event)
    expect(refused.status).toBe(409)
    expect(refused.body.detail.missing).toEqual(expect.arrayContaining(['venue', 'equipment', 'safety']))

    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}`)
    const missing = page.getByTestId('confirm-missing')
    await expect(missing).toContainText('No venue has been booked for this event yet.')
    await expect(missing).toContainText(/neither reserved nor recorded as not required/)
    await expect(missing).toContainText(/safety review/i)
    await expect(page.getByTestId('event-confirm')).toHaveCount(0)

    await page.getByTestId('equipment-not-required-eq1').click()
    await page.getByTestId('equipment-not-required-reason-eq1').fill('The venue has a built-in projector.')
    const saved = page.waitForResponse(
      (response) => /\/equipment-lines\/eq1\/not-required$/.test(response.url()) && response.request().method() === 'POST',
    )
    await page.getByTestId('equipment-not-required-save').click()
    expect((await saved).status()).toBe(200)
    await expect(page.getByTestId('equipment-not-required-line-eq1')).toContainText('built-in projector')
    await expect(missing).not.toContainText(/neither reserved nor recorded/)
    await expect(missing).toContainText('No venue has been booked for this event yet.')
  })

  test('TC-SPM72-AC03 confirming moves the event to Confirmed and records the decider and time', async ({ page }) => {
    const event = await readyToConfirm('SPM72-ac03')
    expect((await confirm(event, 'EO-01')).status).toBe(403)

    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await expect(page.getByTestId('confirm-ready')).toBeVisible()
    const confirmed = page.waitForResponse(
      (response) => /\/confirm$/.test(response.url()) && response.request().method() === 'POST',
    )
    await page.getByTestId('event-confirm').click()
    const response = await confirmed
    expect(response.status()).toBe(200)
    const body = await response.json()
    expect(body).toMatchObject({ status: 'confirmed', decidedBy: 'u2', confirmedBy: 'u2' })
    expect(body.decidedAt).toBeTruthy()
    await expect(page.getByTestId('event-edit-saved')).toContainText('Event confirmed')
    await expect(page.getByTestId('event-confirmation')).toHaveCount(0)

    const stored = await events('GET', `/${event.eventId}`, 'EC-01')
    expect(stored.body).toMatchObject({ status: 'confirmed', confirmedBy: 'u2' })
    expect(stored.body.confirmedAt).toBeTruthy()
    const again = await confirm(event)
    expect(again.status).toBe(409)
    expect(again.body.detail.message).toContain('already confirmed')
  })

  test('TC-SPM72-AC04 the organiser is notified and sees the confirmed venue, date, time, layout, and equipment', async ({
    page,
  }) => {
    const event = await readyToConfirm('SPM72-ac04')
    const confirmed = await confirm(event)
    expect(confirmed.status, JSON.stringify(confirmed.body)).toBe(200)

    const organiser = await inbox('EO-01')
    expect(organiser).toContain(`${event.eventName} is confirmed for`)
    expect(organiser).toContain('Marina Hall A. Layout: Theatre.')

    await login(page, account('EO-01'))
    await page.goto(`/app/events/${event.eventId}`)
    const card = page.getByTestId('organiser-confirmed-arrangements')
    await expect(card).toContainText('Marina Hall A')
    await expect(card).toContainText('Layout: Theatre')
    await expect(card).toContainText('Equipment:')
    await expect(card.getByTestId('organiser-confirmed-date')).not.toBeEmpty()
    await expect(card.getByTestId('organiser-confirmed-time')).not.toBeEmpty()
  })

  test('TC-SPM72-AC05 the venue staff and technical support on the arrangements are notified', async () => {
    const event = await planningEvent('SPM72-ac05')
    await bookVenue(event)
    const requested = await equipmentApi('POST', '/equipment/requests', 'EC-01', {
      eventId: event.eventId,
      equipmentId: 'eq1',
      quantity: 1,
      technicalRequirements: 'AUTO-SPM72 HDMI to the lectern',
      startsAt: event.period.startsAt,
      endsAt: event.period.endsAt,
    })
    expect(requested.status, JSON.stringify(requested.body)).toBe(201)
    const reviewed = await equipmentApi('POST', `/equipment/requests/${requested.body.requestId}/review`, 'TS-01', {
      approve: true,
      reviewNote: 'AUTO-SPM72',
    })
    expect(reviewed.status, JSON.stringify(reviewed.body)).toBe(200)
    const reserved = await equipmentApi('POST', `/equipment/requests/${requested.body.requestId}/reserve`, 'TS-01')
    expect(reserved.status, JSON.stringify(reserved.body)).toBe(201)
    await passSafetyReview(event)

    const confirmed = await confirm(event)
    expect(confirmed.status, JSON.stringify(confirmed.body)).toBe(200)
    for (const accountId of ['VS-01', 'TS-01']) {
      expect(await inbox(accountId), accountId).toContain(`${event.eventName}, which you arranged for, is confirmed`)
    }
  })

  test('TC-SPM72-AC06 attendees see a registration-enabled event once it is confirmed and its registration period opens', async () => {
    const now = Date.now()
    const open = await readyToConfirm('SPM72-ac06-open', {
      registrationEnabled: true,
      registrationOpensAt: new Date(now - DAY).toISOString(),
      registrationClosesAt: new Date(now + 60 * DAY).toISOString(),
    })
    const later = await readyToConfirm('SPM72-ac06-later', {
      registrationEnabled: true,
      registrationOpensAt: new Date(now + 30 * DAY).toISOString(),
      registrationClosesAt: new Date(now + 60 * DAY).toISOString(),
    })
    const browse = async () =>
      (await events('GET', '/open-for-registration', 'ATT-01')).body.map((row) => row.eventId)
    expect(await browse()).not.toContain(open.eventId)

    for (const event of [open, later]) {
      const confirmed = await confirm(event)
      expect(confirmed.status, JSON.stringify(confirmed.body)).toBe(200)
    }
    const listed = await browse()
    expect(listed).toContain(open.eventId)
    expect(listed).not.toContain(later.eventId)
    expect((await events('GET', `/open-for-registration/${later.eventId}`, 'ATT-01')).status).toBe(404)
  })
})
