<template>
  <div class="my-events">
    <p v-if="loading" class="empty-note">Loading your events…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="!events.length" class="empty-note">No requests yet — create one from New Request.</p>

    <div
      v-for="event in events"
      :key="event.eventId"
      class="event-card"
      :data-testid="`organiser-event-${event.eventId}`"
      @click="open(event.eventId)"
    >
      <div class="event-name">{{ event.eventName || 'Untitled event' }}</div>
      <div class="event-meta">
        {{ formatRange(event.proposedStartAt, event.proposedEndAt) }} ·
        <span class="status-pill">{{ event.status }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMyEvents } from '../../api/eventService.js'

const router = useRouter()

const events = ref([])
const loading = ref(true)
const error = ref('')

function formatRange(start, end) {
  if (!start && !end) return 'No date set yet'
  if (!start || !end) return 'Date incomplete'
  return `${new Date(start).toLocaleString()} – ${new Date(end).toLocaleString()}`
}

function open(eventId) {
  router.push(`/app/events/${eventId}`)
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
.my-events { display: flex; flex-direction: column; gap: 12px; max-width: 720px; }

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
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 18px 20px;
  cursor: pointer;
  transition: border-color .4s var(--ease-out), background .4s var(--ease-out);
}
.event-card:hover { border-color: rgba(167, 139, 250, .3); background: var(--glass-strong); }
.event-name { font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 15px; }
.event-meta { font-size: 12px; margin-top: 4px; color: var(--muted); display: flex; align-items: center; gap: 8px; }

.status-pill {
  display: inline-block;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--halo);
  background: rgba(124, 77, 255, .18);
  border: 1px solid rgba(167, 139, 250, .3);
  border-radius: 999px;
  padding: 3px 10px;
}
</style>
