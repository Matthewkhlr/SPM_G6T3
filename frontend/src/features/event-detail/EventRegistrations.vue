<template>
  <div class="event-page">
    <button type="button" class="btn btn-ghost back" @click="goBack">← Event details</button>

    <p v-if="loading" class="empty-note">Loading registrations…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>

    <template v-else>
      <header class="page-head">
        <div>
          <p class="eyebrow">Registrations</p>
          <h1>{{ eventName }}</h1>
        </div>
        <button
          type="button"
          class="btn btn-outline"
          data-testid="filter-hide-withdrawn"
          :aria-pressed="hideWithdrawn"
          @click="hideWithdrawn = !hideWithdrawn"
        >
          {{ hideWithdrawn ? 'Show withdrawn' : 'Hide withdrawn' }}
        </button>
      </header>

      <section class="summary" data-testid="registration-summary">
        <div>
          <span>Capacity</span>
          <strong data-testid="summary-capacity">{{ roster.capacity }}</strong>
        </div>
        <div>
          <span>Registered</span>
          <strong data-testid="summary-registered">{{ roster.registered }}</strong>
        </div>
        <div>
          <span>Withdrawn</span>
          <strong data-testid="summary-withdrawn">{{ roster.withdrawn }}</strong>
        </div>
        <div>
          <span>Places remaining</span>
          <strong data-testid="summary-remaining">{{ roster.remaining }}</strong>
        </div>
      </section>

      <div
        v-if="!roster.attendees.length"
        class="panel empty-state"
        data-testid="registrations-empty"
      >
        <h2>Nobody has registered yet</h2>
        <p>
          Capacity {{ roster.capacity }}. Registration period opens
          {{ formatWhen(roster.registrationOpensAt) }} and closes
          {{ formatWhen(roster.registrationClosesAt) }}.
        </p>
      </div>

      <div v-else class="list">
        <p v-if="!visibleAttendees.length" class="empty-note">Withdrawn registrations are hidden.</p>
        <article
          v-for="row in visibleAttendees"
          :key="row.attendeeRegistrationId"
          class="panel row"
          :class="{ withdrawn: row.status === 'withdrawn' }"
          :data-testid="`registration-${row.attendeeRegistrationId}`"
          :data-registration-status="row.status"
        >
          <div class="row-head">
            <h2>{{ row.attendeeName }}</h2>
            <span class="status-pill" :class="row.status">{{ row.status }}</span>
          </div>
          <dl class="facts">
            <div>
              <dt>Email</dt>
              <dd>{{ row.attendeeEmail }}</dd>
            </div>
            <div>
              <dt>Registered</dt>
              <dd data-testid="registration-created-at">{{ formatWhen(row.createdAt) }}</dd>
            </div>
          </dl>
        </article>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getEvent } from '../../api/eventService.js'
import { getRegistrationRoster } from '../../api/registrationService.js'

const route = useRoute()
const router = useRouter()

const roster = ref(null)
const eventName = ref('Registrations')
const loading = ref(true)
const error = ref('')
const hideWithdrawn = ref(false)

const visibleAttendees = computed(() => {
  const rows = roster.value?.attendees || []
  if (!hideWithdrawn.value) return rows
  return rows.filter((row) => row.status !== 'withdrawn')
})

function formatWhen(value) {
  if (!value) return 'Not set'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'Not set'
  return parsed.toLocaleString()
}

function goBack() {
  router.push(`/app/events/${route.params.id}`)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [eventResult, rosterResult] = await Promise.all([
      getEvent(route.params.id),
      getRegistrationRoster(route.params.id),
    ])
    eventName.value = eventResult.data.eventName || 'Registrations'
    roster.value = rosterResult.data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load registrations. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.event-page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 28px 32px 48px;
}

.back {
  margin: 0 0 18px -18px;
  padding-left: 18px;
}

.empty-note { font-size: 14px; color: var(--muted); }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin-top: 16px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 20px;
  margin-bottom: 22px;
}
.page-head h1 {
  margin: 6px 0 0;
  font-size: 28px;
  font-weight: 500;
  letter-spacing: -.02em;
}

.summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 18px;
}
.summary div {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 14px 16px;
}
.summary span {
  display: block;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 6px;
}
.summary strong {
  font-size: 22px;
  font-weight: 500;
}

.panel {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 22px 24px;
}
.list { display: flex; flex-direction: column; gap: 12px; }
.row.withdrawn {
  opacity: .72;
  border-style: dashed;
}
.row-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.row-head h2 { margin: 0; font-size: 18px; font-weight: 500; }
.empty-state h2 { margin: 0 0 8px; font-size: 18px; font-weight: 500; }
.empty-state p { margin: 0; color: var(--body); line-height: 1.6; }

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
.status-pill.withdrawn {
  color: #FF8A76;
  background: rgba(255, 138, 118, .12);
  border-color: rgba(255, 138, 118, .35);
}

.facts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px 20px; margin: 0; }
.facts dt {
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 4px;
}
.facts dd { margin: 0; font-size: 14px; color: var(--body); line-height: 1.55; }

@media (max-width: 860px) {
  .event-page { padding: 22px 18px 36px; }
  .page-head { flex-direction: column; align-items: stretch; }
  .summary, .facts { grid-template-columns: 1fr 1fr; }
  .back { margin-left: 0; }
}
</style>
