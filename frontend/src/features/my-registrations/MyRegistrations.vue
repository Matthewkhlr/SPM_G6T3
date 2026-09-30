<template>
  <div class="my-registrations">
    <p v-if="loading" class="empty-note">Loading your registrations…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="!rows.length" class="empty-note">You have no registrations yet.</p>

    <button
      v-for="row in rows"
      :key="row.attendeeRegistrationId"
      type="button"
      class="event-card"
      @click="open(row.attendeeRegistrationId)"
    >
      <div class="event-name">{{ row.attendeeName }}</div>
      <div class="event-meta">
        {{ row.eventId }} · {{ row.attendeeEmail }} ·
        <span class="status-pill" :class="row.status">{{ row.status }}</span>
      </div>
    </button>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMyRegistrations } from '../../api/registrationService.js'

const router = useRouter()
const rows = ref([])
const loading = ref(true)
const error = ref('')

function open(registrationId) {
  router.push(`/app/registrations/${registrationId}`)
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
.my-registrations { display: flex; flex-direction: column; gap: 12px; }
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
  text-align: left;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 16px 18px;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.event-name { font-size: 15px; color: var(--text); }
.event-meta { margin-top: 6px; font-size: 13px; color: var(--muted); }
.status-pill {
  display: inline-block;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--halo);
  border: 1px solid rgba(167, 139, 250, .3);
  border-radius: 999px;
  padding: 2px 8px;
}
.status-pill.withdrawn { color: #FFB4A8; border-color: rgba(255, 138, 118, .35); }
</style>
