<template>
  <!-- SPM-116: Venue Staff hold a pending request's venue until a date and time. -->
  <section class="holds" data-testid="venue-holds">
    <h4>Tentative holds</h4>
    <p class="hint">
      Hold a pending request while its coordinator finishes the arrangements. Nobody else can have the venue for
      that time until the hold expires or is released. Times are in UTC.
    </p>
    <p v-if="loadError" class="hold-error" data-testid="venue-holds-error">{{ loadError }}</p>
    <p v-else-if="!requests.length" class="hint" data-testid="venue-holds-none">
      No pending requests for this venue.
    </p>
    <ul v-else>
      <li v-for="request in requests" :key="request.bookingId" :data-testid="`venue-hold-request-${request.bookingId}`">
        <div class="who">
          <strong>{{ eventName(request) }}</strong>
          {{ span(request.startsAt, request.endsAt) }}
        </div>

        <div v-if="request.hold?.state === 'active'" class="state">
          <span class="held" :data-testid="`venue-hold-state-${request.bookingId}`">
            Held until {{ moment(request.hold.expiresAt) }}
          </span>
          <button
            type="button"
            class="btn btn-ghost small"
            :disabled="busyId === request.bookingId"
            :data-testid="`venue-hold-release-${request.bookingId}`"
            @click="release(request)"
          >
            {{ busyId === request.bookingId ? 'Releasing…' : 'Release hold' }}
          </button>
        </div>
        <div v-else class="state">
          <span
            v-if="request.hold?.state === 'expired'"
            class="expired"
            :data-testid="`venue-hold-state-${request.bookingId}`"
          >
            Hold expired {{ moment(request.hold.expiresAt) }}
          </span>
          <label>
            Hold until (UTC)
            <input
              v-model="expiry[request.bookingId]"
              type="datetime-local"
              :data-testid="`venue-hold-until-${request.bookingId}`"
            />
          </label>
          <button
            type="button"
            class="btn btn-solid small"
            :disabled="!expiry[request.bookingId] || busyId === request.bookingId"
            :data-testid="`venue-hold-place-${request.bookingId}`"
            @click="place(request)"
          >
            {{ busyId === request.bookingId ? 'Holding…' : 'Place hold' }}
          </button>
        </div>
        <p v-if="errors[request.bookingId]" class="hold-error" :data-testid="`venue-hold-error-${request.bookingId}`">
          {{ errors[request.bookingId] }}
        </p>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { getVenueBookings, placeVenueHold, releaseVenueHold } from '../../api/venueService.js'

const props = defineProps({ venueId: { type: String, required: true } })

const requests = ref([])
const loadError = ref('')
const busyId = ref('')
const expiry = reactive({})
const errors = reactive({})

// Booking times are UTC and come without a zone marker.
const dayFormat = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' })
const timeFormat = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })

function utc(value) {
  return new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`)
}

function moment(value) {
  const when = utc(value)
  return `${dayFormat.format(when)}, ${timeFormat.format(when)} UTC`
}

function span(start, end) {
  const [from, to] = [utc(start), utc(end)]
  return `${dayFormat.format(from)}, ${timeFormat.format(from)} to ${timeFormat.format(to)} UTC`
}

function eventName(request) {
  const name = request.eventSnapshot?.eventName
  return name ? `"${name}"` : `Event ${request.eventId}`
}

function message(err, fallback) {
  const detail = err.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

async function load() {
  try {
    const { data } = await getVenueBookings({ status: 'pending', venueId: props.venueId })
    requests.value = data
    loadError.value = ''
  } catch {
    loadError.value = 'Unable to load the pending requests for this venue. Please try again.'
  }
}

function replace(updated) {
  requests.value = requests.value.map((row) => (row.bookingId === updated.bookingId ? updated : row))
}

async function place(request) {
  busyId.value = request.bookingId
  errors[request.bookingId] = ''
  try {
    // datetime-local has no timezone; the team reads every time as UTC.
    const { data } = await placeVenueHold(request.bookingId, `${expiry[request.bookingId]}:00Z`)
    replace(data)
    expiry[request.bookingId] = ''
  } catch (err) {
    errors[request.bookingId] = message(err, 'Unable to place the hold. Please try again.')
  } finally {
    busyId.value = ''
  }
}

async function release(request) {
  busyId.value = request.bookingId
  errors[request.bookingId] = ''
  try {
    const { data } = await releaseVenueHold(request.bookingId)
    replace(data)
  } catch (err) {
    errors[request.bookingId] = message(err, 'Unable to release the hold. Please try again.')
  } finally {
    busyId.value = ''
  }
}

watch(() => props.venueId, load)
onMounted(load)
</script>

<style scoped>
.holds { margin-top: 24px; padding-top: 18px; border-top: 1px solid var(--hairline); }
.holds h4 { margin: 0 0 8px; font-size: 14px; font-weight: 500; color: var(--text); }
.hint { margin: 0 0 12px; font-size: 13px; line-height: 1.6; color: var(--muted); }
ul { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 10px; }
li {
  padding: 12px 14px; border-radius: 10px; font-size: 13px; line-height: 1.6; color: var(--body);
  background: rgba(255, 255, 255, .03); border: 1px solid var(--hairline);
}
.who strong { color: var(--text); font-weight: 500; }
.state { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
.state label { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); }
.state input {
  font: inherit; font-size: 13px; color: var(--text); color-scheme: dark;
  background: rgba(255, 255, 255, .03); border: 1px solid var(--hairline); border-radius: 9px; padding: 6px 8px;
}
.held { color: #FFC66D; }
.expired { color: var(--muted); }
.btn.small { padding: 8px 16px; font-size: 12px; }
.hold-error { margin: 8px 0 0; font-size: 13px; color: #FF8A76; }
</style>
