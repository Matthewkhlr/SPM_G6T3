<template>
  <div class="my-registrations">
    <p v-if="loading" class="empty-note">Loading your registrations…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <div v-else-if="!rows.length" data-testid="my-registrations-empty">
      <p class="empty-note">You have no registrations yet. Browse events to find one.</p>
      <button type="button" class="btn btn-solid" data-testid="empty-browse-events" @click="browse">
        Browse events
      </button>
    </div>
    <template v-else>
      <section data-testid="my-registrations-upcoming">
        <h3>Upcoming</h3>
        <button
          v-for="row in upcoming"
          :key="row.attendeeRegistrationId"
          type="button"
          class="event-card"
          :data-testid="`my-registration-${row.eventId}`"
          :data-cancelled="row.cancelled ? 'true' : 'false'"
          :data-changed="row.changed ? 'true' : 'false'"
          @click="open(row.attendeeRegistrationId)"
        >
          <div class="event-name">{{ row.eventName || row.eventId }}</div>
          <div class="event-meta">
            <span data-testid="reg-date">{{ datePart(row.proposedStartAt || row.startsAt) }}</span>
            · <span data-testid="reg-start">{{ timePart(row.proposedStartAt || row.startsAt) }}</span>
            – <span data-testid="reg-end">{{ timePart(row.proposedEndAt || row.endsAt) }}</span>
          </div>
          <p>{{ row.venueName }} · {{ row.venueLocation }}</p>
          <p>{{ row.cancelled ? 'Cancelled' : row.status }}<template v-if="row.changed"> · Changed</template></p>
        </button>
      </section>
      <section v-if="past.length" data-testid="my-registrations-past">
        <h3>Past</h3>
        <button
          v-for="row in past"
          :key="row.attendeeRegistrationId"
          type="button"
          class="event-card"
          :data-testid="`my-registration-${row.eventId}`"
          @click="open(row.attendeeRegistrationId)"
        >
          <div class="event-name">{{ row.eventName || row.eventId }}</div>
        </button>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMyRegistrations } from '../../api/registrationService.js'

const router = useRouter()
const rows = ref([])
const loading = ref(true)
const error = ref('')

const upcoming = computed(() => rows.value.filter((row) => !isPast(row)))
const past = computed(() => rows.value.filter((row) => isPast(row)))

function isPast(row) {
  const end = row.proposedEndAt || row.endsAt || row.proposedStartAt || row.startsAt
  if (!end) return false
  return new Date(end).getTime() < Date.now()
}

function datePart(value) {
  return value ? new Date(value).toLocaleDateString() : ''
}

function timePart(value) {
  return value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
}

function open(registrationId) {
  router.push(`/app/registrations/${registrationId}`)
}

function browse() {
  router.push('/app')
}

onMounted(async () => {
  try {
    const response = await getMyRegistrations()
    rows.value = response.data
  } catch (err) {
    const message = err.response?.data?.detail
    error.value = typeof message === 'string' ? message : 'Could not load your registrations.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.my-registrations, section { display: flex; flex-direction: column; gap: 12px; }
.empty-note { font-size: 14px; color: var(--muted); }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
}
.event-card {
  text-align: left;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 16px 18px;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.event-name { font-size: 15px; }
.event-meta { margin-top: 6px; font-size: 13px; color: var(--muted); }
</style>
