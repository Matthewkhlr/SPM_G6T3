<template>
  <div class="venue-select-page">
    <button type="button" class="btn btn-ghost small back" @click="router.push(`/app/events/${eventId}`)">
      ← Back to event
    </button>

    <p v-if="!canCheck" class="form-error">Only Event Coordinators can choose a venue for an event.</p>
    <p v-else-if="loading" class="empty-note">Loading…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>

    <template v-else>
      <div class="event-summary">
        <h2>Choose venues for {{ event.eventName }}</h2>
        <p>
          {{ formatRange(event.proposedStartAt, event.proposedEndAt) }} ·
          {{ event.expectedAttendance }} expected
          <template v-if="event.layoutPreference"> · {{ event.layoutPreference }} layout</template>
        </p>
      </div>

      <!-- SPM-46 AC2: everyone else may check venues but not act on this event. -->
      <p v-if="!isAssignedCoordinator" class="read-only-note" data-testid="venue-request-read-only">
        Only the coordinator assigned to this event can request, withdraw, or cancel a venue for it. You can still
        check how each venue suits the event.
      </p>

      <div class="arrangement" :class="{ complete: arrangementsComplete }" data-testid="venue-arrangement">
        <p>{{ arrangementText }}</p>
        <ul v-if="bookings.length" class="booking-list">
          <li v-for="booking in bookings" :key="booking.bookingId" :data-testid="`venue-booking-${booking.status}`">
            <span>
              <strong>{{ venueNameFor(booking.venueId) }}</strong>
              · {{ statusLabel(booking.status) }}
              <template v-if="booking.createdAt"> · sent {{ formatUtc(booking.createdAt) }} UTC</template>
              <!-- SPM-116: Venue Staff are holding this venue while the arrangements are finished. -->
              <span
                v-if="booking.hold && ['active', 'expired'].includes(booking.hold.state)"
                class="hold-tag"
                :class="booking.hold.state"
                :data-testid="`venue-hold-${booking.bookingId}`"
              >
                {{ booking.hold.state === 'active' ? 'Held until' : 'Hold expired' }}
                {{ formatUtc(booking.hold.expiresAt) }} UTC
              </span>
            </span>
            <button
              v-if="isAssignedCoordinator && booking.status === 'pending'"
              type="button"
              class="btn btn-ghost small"
              data-testid="venue-request-withdraw"
              :disabled="busyId === booking.bookingId"
              @click="withdraw(booking)"
            >
              {{ busyId === booking.bookingId ? 'Withdrawing…' : 'Withdraw request' }}
            </button>
            <button
              v-else-if="isAssignedCoordinator && booking.status === 'approved'"
              type="button"
              class="btn btn-ghost small"
              data-testid="venue-booking-cancel"
              :disabled="busyId === booking.bookingId"
              @click="cancel(booking)"
            >
              {{ busyId === booking.bookingId ? 'Cancelling…' : 'Cancel this booking' }}
            </button>
          </li>
        </ul>
      </div>
      <p v-if="actionError" class="form-error">{{ actionError }}</p>
      <p v-if="notice" class="success-note" data-testid="venue-request-result">{{ notice }}</p>

      <!-- SPM-61: search narrows the list below; until then every venue is listed. -->
      <VenueSearch :event="event" :venues="venues" @results="searchResults = $event" />

      <div class="layout">
        <div class="venue-list">
          <div
            v-for="venue in shownVenues"
            :key="venue.venueId"
            class="venue-row"
            :class="{ active: selectedId === venue.venueId }"
            :data-testid="`venue-select-${venue.venueId}`"
            @click="selectVenue(venue)"
          >
            <div class="venue-name">{{ venue.name }}</div>
            <div v-if="searchResults" class="venue-meta">
              {{ venue.location }} · Capacity {{ venue.layoutCapacity }}
              {{ venue.layout ? `in ${venue.layout}` : 'at most' }} · {{ venue.headroom }} spare
            </div>
            <div v-else class="venue-meta">{{ venue.location }} · Capacity {{ venue.capacity }}</div>
            <span
              v-if="venue.contested"
              class="contested"
              :data-testid="`venue-contested-${venue.venueId}`"
            >Contested: another event's request for this time is waiting for Venue Staff</span>
            <!-- SPM-62 AC9: the same verdict the check below gives when this venue is picked. -->
            <span
              v-if="venue.verdict"
              class="row-verdict"
              :class="VERDICT_CLASSES[venue.verdict]"
              :data-testid="`venue-verdict-${venue.venueId}`"
            >{{ VERDICT_LABELS[venue.verdict] }}</span>
          </div>
          <p v-if="!shownVenues.length" class="empty-note">
            {{ searchResults ? 'No venue fits these requirements.' : 'No venues are currently available.' }}
          </p>
        </div>

        <div class="verdict-panel">
          <p v-if="!selectedId" class="empty-note">Select a venue to check whether it suits this event.</p>
          <p v-else-if="checking" class="empty-note">Checking {{ selectedName }}…</p>
          <p v-else-if="checkError" class="form-error">{{ checkError }}</p>

          <template v-else-if="result">
            <h3>{{ selectedName }}</h3>
            <div class="verdict" :class="verdictClass" data-testid="suitability-verdict">
              {{ VERDICT_LABELS[result.verdict] }}
            </div>

            <ul v-if="result.reasons.length" class="reasons" data-testid="suitability-reasons">
              <li v-for="(reason, i) in result.reasons" :key="i" :class="reason.severity">
                <span class="tag">{{ reason.severity === 'failure' ? 'Failure' : 'Warning' }}</span>
                {{ reason.message }}
              </li>
            </ul>
            <p v-else class="hint all-clear">This venue meets every requirement for this event.</p>

            <!-- SPM-62 AC8 and SPM-63 AC3/AC4: failures block; warnings go ahead once acknowledged. -->
            <template v-if="isAssignedCoordinator">
              <label v-if="result.verdict === 'suitable with warnings'" class="acknowledge">
                <input v-model="acknowledged" type="checkbox" data-testid="suitability-acknowledge" />
                I have read the warnings above and want to send the request anyway.
              </label>
              <label v-if="result.verdict !== 'not suitable'" class="notes">
                Notes for Venue Staff (optional)
                <textarea v-model="notes" rows="3" maxlength="1000" data-testid="venue-request-notes" />
              </label>
              <div class="request-row">
                <button
                  type="button"
                  class="btn btn-solid"
                  data-testid="venue-request-submit"
                  :disabled="!canSubmit"
                  @click="requestVenue"
                >
                  {{ submitting ? 'Sending…' : 'Request this venue' }}
                </button>
                <p v-if="submitHint" class="hint">{{ submitHint }}</p>
              </div>
              <p v-if="requestError" class="form-error request-error">{{ requestError }}</p>
            </template>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getEvent } from '../../api/eventService.js'
import {
  checkSuitability,
  cancelVenueBooking,
  getVenueBookings,
  getVenues,
  requestVenueBooking,
  withdrawVenueBooking,
} from '../../api/venueService.js'
import { session } from '../../store/session.js'
import VenueSearch from './VenueSearch.vue'

const VERDICT_LABELS = {
  suitable: 'Suitable',
  'suitable with warnings': 'Suitable with warnings',
  'not suitable': 'Not suitable',
}

const route = useRoute()
const router = useRouter()
const eventId = route.params.id

const canCheck = computed(() => session.role === 'coordinator')
const event = ref(null)
const venues = ref([])
// SPM-61: the shortlist from the last search, or null to list every venue.
const searchResults = ref(null)
const shownVenues = computed(() => searchResults.value ?? venues.value)
const loading = ref(true)
const error = ref('')

const selectedId = ref(null)
const selectedName = ref('')
const checking = ref(false)
const checkError = ref('')
const result = ref(null)

// SPM-63: the request itself.
const PLANNING_STATUSES = ['approved', 'planning']
const bookings = ref([]) // this event's venue requests
const acknowledged = ref(false)
const notes = ref('')
const submitting = ref(false)
const requestError = ref('')
const busyId = ref('')
const actionError = ref('')
const notice = ref('')
const STATUS_LABELS = {
  pending: 'Pending',
  approved: 'Approved',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
  cancelled: 'Cancelled',
}

// SPM-46 AC1: only the event's assigned coordinator requests or withdraws a
// venue. The server enforces the same; this only decides what to offer.
const isAssignedCoordinator = computed(
  () =>
    session.role === 'coordinator' &&
    !!event.value?.coordinatorId &&
    event.value.coordinatorId === session.userId,
)
const openBookings = computed(() =>
  bookings.value.filter((booking) => booking.status === 'pending' || booking.status === 'approved'),
)
const arrangementsComplete = computed(
  () => openBookings.value.length > 0 && openBookings.value.every((booking) => booking.status === 'approved'),
)
const selectedAlreadyBooked = computed(() =>
  openBookings.value.some((booking) => booking.venueId === selectedId.value),
)
const arrangementText = computed(() => {
  if (!openBookings.value.length) return 'No venues are requested for this event yet.'
  if (arrangementsComplete.value) return 'Venue arrangements are complete. Every requested venue is approved.'
  return 'Venue arrangements are not complete until every requested venue is approved.'
})
const hasDates = computed(() => Boolean(event.value?.proposedStartAt && event.value?.proposedEndAt))
const inPlanning = computed(() => PLANNING_STATUSES.includes(event.value?.status))

const canSubmit = computed(() => Boolean(
  result.value
    && result.value.verdict !== 'not suitable'
    && (result.value.verdict !== 'suitable with warnings' || acknowledged.value)
    && !selectedAlreadyBooked.value
    && hasDates.value
    && inPlanning.value
    && !submitting.value,
))

// Why the button is off, in plain words (the most blocking reason first).
const submitHint = computed(() => {
  if (!result.value) return ''
  if (result.value.verdict === 'not suitable') return 'This venue cannot be requested until every failure above is resolved.'
  if (!inPlanning.value) return 'A venue can be requested once the event has been approved for planning.'
  if (!hasDates.value) return "Add the event's date and time before requesting a venue."
  if (selectedAlreadyBooked.value) {
    return 'This event already has a booking for this venue. Withdraw, reject, or cancel it before requesting it again.'
  }
  if (result.value.verdict === 'suitable with warnings' && !acknowledged.value) {
    return 'Tick the box above to confirm you have read the warnings.'
  }
  return ''
})

function statusLabel(status) {
  return STATUS_LABELS[status] || status
}

// Only the latest click may show its verdict, so a slow check for an earlier
// venue can never appear under the venue picked after it.
let checkToken = 0

const VERDICT_CLASSES = {
  suitable: 'ok',
  'suitable with warnings': 'warn',
  'not suitable': 'fail',
}

const verdictClass = computed(() => VERDICT_CLASSES[result.value?.verdict])

// The team shows every time in UTC until the customer specifies a timezone.
function formatUtc(iso) {
  const withZone = /Z|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`
  return new Date(withZone).toLocaleString('en-SG', {
    timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true,
  })
}

function formatRange(start, end) {
  if (!start || !end) return 'No date set yet'
  return `${formatUtc(start)} to ${formatUtc(end)} UTC`
}

async function selectVenue(venue) {
  const token = ++checkToken
  selectedId.value = venue.venueId
  selectedName.value = venue.name
  result.value = null
  checkError.value = ''
  requestError.value = ''
  acknowledged.value = false
  checking.value = true
  try {
    const { data } = await checkSuitability(eventId, venue.venueId)
    if (token === checkToken) result.value = data
  } catch (err) {
    if (token === checkToken) {
      checkError.value = err.response?.data?.detail || 'Unable to check this venue right now. Please try again.'
    }
  } finally {
    if (token === checkToken) checking.value = false
  }
}

function venueNameFor(venueId) {
  return venues.value.find((v) => v.venueId === venueId)?.name || 'another venue'
}

// SPM-63 AC2: the request uses the event's own dates; the server adds the
// rest of the event's facts, the venue's setup and turnaround (SPM-64), and
// runs the suitability check again.
async function requestVenue() {
  submitting.value = true
  requestError.value = ''
  notice.value = ''
  try {
    const { data } = await requestVenueBooking({
      eventId,
      venueId: selectedId.value,
      startsAt: event.value.proposedStartAt,
      endsAt: event.value.proposedEndAt,
      coordinatorNotes: notes.value.trim(),
      acknowledgeWarnings: acknowledged.value,
    })
    bookings.value = [...bookings.value, data]
    notice.value = `Request submitted for ${selectedName.value}. It is now pending with Venue Staff.`
    notes.value = ''
    acknowledged.value = false
  } catch (err) {
    requestError.value = err.response?.data?.detail || 'Unable to send this request right now. Please try again.'
  } finally {
    submitting.value = false
  }
}

async function withdraw(booking) {
  busyId.value = booking.bookingId
  actionError.value = ''
  notice.value = ''
  try {
    const { data } = await withdrawVenueBooking(booking.bookingId)
    bookings.value = bookings.value.map((row) => (row.bookingId === data.bookingId ? data : row))
    notice.value = `Request withdrawn for ${venueNameFor(booking.venueId)}. The event's other venue bookings are unchanged.`
  } catch (err) {
    actionError.value = err.response?.data?.detail || 'Unable to withdraw this request right now. Please try again.'
  } finally {
    busyId.value = ''
  }
}

async function cancel(booking) {
  busyId.value = booking.bookingId
  actionError.value = ''
  notice.value = ''
  try {
    const { data } = await cancelVenueBooking(booking.bookingId)
    bookings.value = bookings.value.map((row) => (row.bookingId === data.bookingId ? data : row))
    notice.value = `Booking cancelled for ${venueNameFor(booking.venueId)}. The event's other venue bookings are unchanged.`
  } catch (err) {
    actionError.value = err.response?.data?.detail || 'Unable to cancel this booking right now. Please try again.'
  } finally {
    busyId.value = ''
  }
}

onMounted(async () => {
  if (!canCheck.value) return
  try {
    const [eventResponse, venuesResponse, bookingsResponse] = await Promise.all([
      getEvent(eventId),
      getVenues(),
      getVenueBookings({ eventId }),
    ])
    event.value = eventResponse.data
    venues.value = venuesResponse.data
    bookings.value = bookingsResponse.data
  } catch (err) {
    error.value = err.response?.status === 404
      ? 'This event could not be found.'
      : 'Unable to load this event and the venue list. Please try again.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.venue-select-page { max-width: 980px; margin: 0 auto; padding: 32px 24px; }
.back { margin-bottom: 18px; }

.empty-note { font-size: 14px; color: var(--muted); }
.form-error {
  color: #FF8A76; font-size: 13px;
  background: rgba(255, 138, 118, .08); border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px; padding: 11px 14px;
}
.hint { font-size: 13px; color: var(--muted); margin: 0; line-height: 1.6; }
.all-clear { margin-bottom: 18px; }
.request-error { margin-top: 14px; }

.arrangement {
  margin: 0 0 18px; padding: 14px 16px; border-radius: 12px;
  background: rgba(255, 198, 109, .08); border: 1px solid rgba(255, 198, 109, .3);
}
.arrangement.complete {
  background: rgba(56, 224, 200, .08); border-color: rgba(56, 224, 200, .3);
}
.arrangement p { margin: 0; font-size: 13px; color: var(--text); line-height: 1.6; }
.booking-list { list-style: none; margin: 12px 0 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.hold-tag {
  display: inline-block; margin-left: 6px; padding: 1px 8px; border-radius: 999px; font-size: 11px;
}
.hold-tag.active { color: #FFC66D; background: rgba(255, 198, 109, .15); }
.hold-tag.expired { color: var(--muted); background: rgba(255, 255, 255, .06); }
.booking-list li {
  display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  font-size: 13px; color: var(--text);
}
.read-only-note {
  margin: 0 0 18px; padding: 11px 14px; border-radius: 9px; font-size: 13px; line-height: 1.6;
  color: var(--body); background: var(--glass); border: 1px solid var(--hairline);
}
.success-note {
  margin: 0 0 18px; padding: 11px 14px; border-radius: 9px; font-size: 13px;
  color: var(--signal); background: rgba(56, 224, 200, .08); border: 1px solid rgba(56, 224, 200, .25);
}

.acknowledge {
  display: flex; align-items: flex-start; gap: 8px; margin: 0 0 14px;
  font-size: 13px; color: var(--text); line-height: 1.5; cursor: pointer;
}
.acknowledge input { margin-top: 3px; accent-color: var(--iris); }
.notes { display: flex; flex-direction: column; gap: 6px; margin: 0 0 14px; font-size: 12px; color: var(--muted); }
.notes textarea {
  font: inherit; font-size: 13px; color: var(--text); resize: vertical;
  background: rgba(255, 255, 255, .03); border: 1px solid var(--hairline); border-radius: 9px; padding: 9px 11px;
}

.event-summary h2 { margin: 0 0 6px; font-size: 22px; font-weight: 500; }
.event-summary p { margin: 0 0 22px; font-size: 14px; color: var(--body); }

.layout { display: grid; grid-template-columns: 290px 1fr; gap: 20px; align-items: start; }

.venue-list { display: flex; flex-direction: column; gap: 8px; }
.venue-row {
  background: var(--glass); border: 1px solid var(--hairline);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-radius: 12px; padding: 14px 16px; cursor: pointer;
  transition: background .4s var(--ease-out), border-color .4s var(--ease-out), transform .4s var(--ease-out);
}
.venue-row:hover { background: var(--glass-strong); transform: translateX(3px); }
.venue-row.active {
  border-color: rgba(167, 139, 250, .55);
  background: linear-gradient(90deg, rgba(124, 77, 255, .22), rgba(124, 77, 255, .04));
}
.venue-name { font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 14px; }
.venue-meta { font-size: 12px; margin-top: 3px; color: var(--muted); }
.contested {
  display: inline-block; margin-top: 6px; padding: 2px 8px; border-radius: 999px; font-size: 11px;
  color: var(--text); background: rgba(255, 198, 109, .12); border: 1px solid rgba(255, 198, 109, .35);
}
.row-verdict {
  display: inline-block; margin: 6px 0 0 6px; padding: 2px 8px; border-radius: 999px;
  font-size: 11px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase;
}
.row-verdict.ok { color: var(--signal); background: rgba(56, 224, 200, .15); }
.row-verdict.warn { color: #FFC66D; background: rgba(255, 198, 109, .15); }
.row-verdict.fail { color: #FF8A76; background: rgba(255, 138, 118, .15); }

.verdict-panel {
  background: var(--glass); border: 1px solid var(--hairline);
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  border-radius: 16px; padding: 26px; min-height: 140px;
  /* Stays in view while a long venue list scrolls, so a click always shows its verdict. */
  position: sticky; top: 24px;
}
.verdict-panel h3 { margin: 0 0 12px; font-size: 19px; font-weight: 500; }

.verdict {
  display: inline-block; font-size: 12px; letter-spacing: .06em; text-transform: uppercase; font-weight: 600;
  padding: 5px 12px; border-radius: 999px; margin-bottom: 16px;
}
.verdict.ok { color: var(--signal); background: rgba(56, 224, 200, .15); }
.verdict.warn { color: #FFC66D; background: rgba(255, 198, 109, .15); }
.verdict.fail { color: #FF8A76; background: rgba(255, 138, 118, .15); }

.reasons { list-style: none; margin: 0 0 18px; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.reasons li {
  font-size: 13px; line-height: 1.6; color: var(--text);
  padding: 8px 12px; border-radius: 0 8px 8px 0; border-left: 2px solid var(--hairline);
  background: rgba(255, 255, 255, .02);
}
.reasons li.failure { border-left-color: #FF8A76; }
.reasons li.warning { border-left-color: #FFC66D; }
.tag { font-size: 10px; letter-spacing: .06em; text-transform: uppercase; font-weight: 700; margin-right: 6px; }
.failure .tag { color: #FF8A76; }
.warning .tag { color: #FFC66D; }

.request-row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-top: 4px; }
.btn.small { padding: 6px 14px; font-size: 12px; }
.btn:disabled { opacity: .45; cursor: not-allowed; }

@media (max-width: 720px) {
  .layout { grid-template-columns: 1fr; }
}
</style>
