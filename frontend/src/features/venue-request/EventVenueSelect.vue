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
        <h2>Choose a venue for {{ event.eventName }}</h2>
        <p>
          {{ formatRange(event.proposedStartAt, event.proposedEndAt) }} ·
          {{ event.expectedAttendance }} expected
          <template v-if="event.layoutPreference"> · {{ event.layoutPreference }} layout</template>
        </p>
      </div>

      <!-- SPM-63 AC7 and AC8: one pending request per event; the coordinator can withdraw it. -->
      <div v-if="pendingRequest" class="pending-banner" data-testid="venue-request-pending">
        <p>
          A request for <strong>{{ venueNameFor(pendingRequest.venueId) }}</strong> is waiting for Venue Staff
          (sent {{ formatUtc(pendingRequest.createdAt) }} UTC). Withdraw it before requesting a different venue.
        </p>
        <button
          type="button"
          class="btn btn-ghost small"
          data-testid="venue-request-withdraw"
          :disabled="withdrawing"
          @click="withdraw"
        >
          {{ withdrawing ? 'Withdrawing…' : 'Withdraw request' }}
        </button>
      </div>
      <p v-if="withdrawError" class="form-error">{{ withdrawError }}</p>
      <p v-if="notice" class="success-note" data-testid="venue-request-result">{{ notice }}</p>

      <div class="layout">
        <div class="venue-list">
          <div
            v-for="venue in venues"
            :key="venue.venueId"
            class="venue-row"
            :class="{ active: selectedId === venue.venueId }"
            :data-testid="`venue-select-${venue.venueId}`"
            @click="selectVenue(venue)"
          >
            <div class="venue-name">{{ venue.name }}</div>
            <div class="venue-meta">{{ venue.location }} · Capacity {{ venue.capacity }}</div>
          </div>
          <p v-if="!venues.length" class="empty-note">No venues are currently available.</p>
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
  getVenueBookings,
  getVenues,
  requestVenueBooking,
  withdrawVenueBooking,
} from '../../api/venueService.js'
import { session } from '../../store/session.js'

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
const withdrawing = ref(false)
const withdrawError = ref('')
const notice = ref('')

const pendingRequest = computed(() => bookings.value.find((b) => b.status === 'pending') || null)
const hasDates = computed(() => Boolean(event.value?.proposedStartAt && event.value?.proposedEndAt))
const inPlanning = computed(() => PLANNING_STATUSES.includes(event.value?.status))

const canSubmit = computed(() => Boolean(
  result.value
    && result.value.verdict !== 'not suitable'
    && (result.value.verdict !== 'suitable with warnings' || acknowledged.value)
    && !pendingRequest.value
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
  if (pendingRequest.value) return 'This event already has a pending request. Withdraw it first to request this venue.'
  if (result.value.verdict === 'suitable with warnings' && !acknowledged.value) {
    return 'Tick the box above to confirm you have read the warnings.'
  }
  return ''
})

// Only the latest click may show its verdict, so a slow check for an earlier
// venue can never appear under the venue picked after it.
let checkToken = 0

const verdictClass = computed(() => ({
  suitable: 'ok',
  'suitable with warnings': 'warn',
  'not suitable': 'fail',
})[result.value?.verdict])

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
// rest of the event's facts and runs the suitability check again.
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
      setupStartsAt: event.value.proposedStartAt,
      teardownEndsAt: event.value.proposedEndAt,
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

async function withdraw() {
  withdrawing.value = true
  withdrawError.value = ''
  notice.value = ''
  try {
    const { data } = await withdrawVenueBooking(pendingRequest.value.bookingId)
    bookings.value = bookings.value.map((b) => (b.bookingId === data.bookingId ? data : b))
    notice.value = 'Request withdrawn. Venue Staff have been told, and you can now request a different venue.'
  } catch (err) {
    withdrawError.value = err.response?.data?.detail || 'Unable to withdraw this request right now. Please try again.'
  } finally {
    withdrawing.value = false
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

.pending-banner {
  display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap;
  margin: 0 0 18px; padding: 14px 16px; border-radius: 12px;
  background: rgba(255, 198, 109, .08); border: 1px solid rgba(255, 198, 109, .3);
}
.pending-banner p { margin: 0; font-size: 13px; color: var(--text); line-height: 1.6; }
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
