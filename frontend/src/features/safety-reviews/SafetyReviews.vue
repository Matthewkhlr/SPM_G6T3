<template>
  <!-- SPM-120: events whose venue and equipment are confirmed, waiting on a Safety Officer. -->
  <div class="safety-reviews">
    <p v-if="loading" class="empty-note">Loading safety reviews…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="!reviews.length" class="empty-note" data-testid="safety-queue-empty">
      No events are waiting for a safety review.
    </p>

    <button
      v-for="review in reviews"
      :key="review.reviewId"
      type="button"
      class="event-card"
      :data-testid="`safety-queue-${review.eventId}`"
      @click="open(review.eventId)"
    >
      <span class="event-name">{{ review.package.eventName }}</span>
      <span class="event-meta">
        <span>{{ formatRange(review.package.proposedStartAt, review.package.proposedEndAt) }}</span>
        <span>{{ review.package.expectedAttendance }} attendees</span>
        <span>{{ review.package.venues.map((venue) => venue.venueName).join(', ') }}</span>
        <span>Submitted {{ formatUtc(review.submittedAt) }}</span>
      </span>
      <span v-if="hasFlag(review)" class="flag">An arrangement is marked for re-checking</span>
    </button>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getSafetyReviewQueue } from '../../api/eventService.js'
import { formatUtc } from '../../utils/datetime.js'

const router = useRouter()
const reviews = ref([])
const loading = ref(true)
const error = ref('')

function formatRange(start, end) {
  if (!start || !end) return 'Date not set'
  return `${new Date(start).toLocaleString()} – ${new Date(end).toLocaleString()}`
}

function hasFlag(review) {
  const { venues, equipment } = review.package
  return venues.some((venue) => venue.needsReverification) || equipment.some((line) => line.needsReverification)
}

function open(eventId) {
  router.push(`/app/events/${eventId}`)
}

async function load() {
  try {
    const { data } = await getSafetyReviewQueue()
    reviews.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load the safety reviews. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.safety-reviews { display: flex; flex-direction: column; gap: 12px; max-width: 760px; }
.empty-note { font-size: 14px; color: var(--muted); }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
}
.event-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  text-align: left;
  font: inherit;
  color: inherit;
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 18px 20px;
  cursor: pointer;
  transition: border-color .4s var(--ease-out), background .4s var(--ease-out);
}
.event-card:hover { border-color: rgba(167, 139, 250, .3); background: var(--glass-strong); }
.event-card:focus-visible { outline: none; border-color: rgba(167, 139, 250, .6); box-shadow: 0 0 0 3px rgba(124, 77, 255, .16); }
.event-name { font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 15px; }
.event-meta { font-size: 12px; color: var(--muted); display: flex; flex-wrap: wrap; gap: 6px 14px; }
.flag {
  align-self: flex-start;
  font-size: 10px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #FFD9A8;
  background: rgba(255, 170, 80, .1);
  border: 1px solid rgba(255, 196, 120, .35);
  border-radius: 999px;
  padding: 2px 9px;
}
</style>
