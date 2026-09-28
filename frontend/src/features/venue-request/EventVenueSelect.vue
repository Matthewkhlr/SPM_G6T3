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

            <!-- AC8: warnings may go ahead, failures may not. -->
            <div class="request-row">
              <button
                type="button"
                class="btn btn-solid"
                data-testid="venue-request-submit"
                :disabled="result.verdict === 'not suitable'"
                @click="requestVenue"
              >
                Request this venue
              </button>
              <p class="hint">
                <template v-if="result.verdict === 'not suitable'">
                  This venue cannot be requested until every failure above is resolved.
                </template>
                <template v-else-if="result.verdict === 'suitable with warnings'">
                  You can still request this venue. Please read the warnings above first.
                </template>
              </p>
            </div>
            <p v-if="requestNote" class="hint note">{{ requestNote }}</p>
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
import { checkSuitability, getVenues } from '../../api/venueService.js'
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
const requestNote = ref('')

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
  requestNote.value = ''
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

function requestVenue() {
  // Sending the booking request to Venue Staff is SPM-63.
  requestNote.value = 'Sending venue booking requests is not available yet. It is coming in the next update.'
}

onMounted(async () => {
  if (!canCheck.value) return
  try {
    const [eventResponse, venuesResponse] = await Promise.all([getEvent(eventId), getVenues()])
    event.value = eventResponse.data
    venues.value = venuesResponse.data
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
.note { margin-top: 12px; }
.all-clear { margin-bottom: 18px; }

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
