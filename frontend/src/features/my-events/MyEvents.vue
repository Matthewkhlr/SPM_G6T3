<template>
  <div class="my-events">
    <p v-if="loading" class="empty-note">Loading your events…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <div v-else-if="!events.length" data-testid="organiser-events-empty">
      <p class="empty-note">Create your first request to get started.</p>
      <button type="button" class="btn btn-solid" data-testid="organiser-empty-create" @click="create">
        New request
      </button>
    </div>

    <div v-else data-testid="organiser-event-list" class="list">
      <div
        v-for="event in events"
        :key="event.eventId"
        class="event-card"
        :data-testid="`organiser-event-${event.eventId}`"
        :data-lifecycle="lifecycle(event.status)"
        @click="open(event.eventId)"
      >
        <div class="event-name">{{ event.eventName || 'Untitled event' }}</div>
        <div class="event-meta">
          <span :data-testid="`organiser-event-${event.eventId}-date`">
            {{ formatRange(event.proposedStartAt, event.proposedEndAt) }}
          </span>
          ·
          <span class="status-pill" :data-testid="`organiser-event-${event.eventId}-status`">
            {{ eventStatusLabel(event.status) }}
          </span>
          <template v-if="safetyNote(event)">
            ·
            <span class="safety-note" :data-testid="`organiser-event-${event.eventId}-safety`">
              {{ safetyNote(event) }}
            </span>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMyEvents } from '../../api/eventService.js'
import { SAFETY_SUBMITTABLE_STATUSES, eventStatusLabel } from '../../config/eventStatus.js'

const router = useRouter()
const emit = defineEmits(['create'])

const events = ref([])
const loading = ref(true)
const error = ref('')

function lifecycle(status) {
  if (status === 'draft') return 'draft'
  if (status === 'submitted') return 'submitted'
  return status
}

// SPM-121 AC5: an event back in planning after its safety review says why.
// One waiting on the review already reads so from its status.
const SAFETY_NOTES = {
  changes_requested: 'Safety changes requested',
  rejected: 'Safety review rejected',
}

function safetyNote(event) {
  if (!SAFETY_SUBMITTABLE_STATUSES.includes(event.status)) return ''
  return SAFETY_NOTES[event.safetyReviewStatus] || ''
}

function formatRange(start, end) {
  if (!start && !end) return 'No date set yet'
  if (!start || !end) return 'Date incomplete'
  return `${new Date(start).toLocaleString()} – ${new Date(end).toLocaleString()}`
}

function open(eventId) {
  router.push(`/app/events/${eventId}`)
}

function create() {
  emit('create')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getMyEvents()
    events.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load your events. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.my-events, .list { display: flex; flex-direction: column; gap: 12px; max-width: 720px; }
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
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 18px 20px;
  cursor: pointer;
}
.event-name { font-size: 15px; color: var(--text); }
.event-meta { margin-top: 6px; font-size: 13px; color: var(--muted); }
.safety-note { color: #FFD9A8; }
</style>
