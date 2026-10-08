<template>
  <div class="assigned-events">
    <p v-if="loading" class="empty-note">Loading assigned events…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="!events.length" class="empty-note">No events are assigned to you yet.</p>

    <template v-else>
      <div class="toolbar">
        <label class="search">
          Search
          <input v-model="query" type="search" placeholder="Event name" />
        </label>
        <label>
          From
          <input v-model="fromDate" type="date" />
        </label>
        <label>
          To
          <input v-model="toDate" type="date" />
        </label>
        <button v-if="filtersActive" type="button" class="btn btn-ghost clear" @click="clearFilters">
          Clear
        </button>
      </div>
      <p v-if="dateRangeInvalid" class="hint">The From date is after the To date.</p>

      <div class="flags">
        <button
          type="button"
          class="flag"
          :class="{ active: !statusFilter }"
          @click="statusFilter = ''"
        >
          All <span>{{ narrowed.length }}</span>
        </button>
        <button
          v-for="flag in flags"
          :key="flag.status"
          type="button"
          class="flag"
          :class="{ active: statusFilter === flag.status, empty: flag.count === 0 }"
          @click="toggleStatus(flag.status)"
        >
          {{ statusLabel(flag.status) }} <span>{{ flag.count }}</span>
        </button>
      </div>

      <p v-if="!visible.length" class="empty-note">No assigned events match this search.</p>

      <button
        v-for="event in visible"
        :key="event.eventId"
        type="button"
        class="event-card"
        @click="open(event.eventId)"
      >
        <div class="event-name">{{ event.eventName || 'Untitled event' }}</div>
        <div class="event-meta">
          {{ formatRange(event.proposedStartAt, event.proposedEndAt) }}
          <span class="status-pill">{{ statusLabel(event.status) }}</span>
        </div>
      </button>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getEvents } from '../../api/eventService.js'
import { session } from '../../store/session.js'

const STATUS_ORDER = [
  'submitted',
  'under review',
  'approved',
  'rejected',
  'planning',
  'safety review',
  'safety approved',
  'preparing',
  'prepared',
  'reconsidering',
  'confirmed',
  'cancelled',
  'completed',
]

const router = useRouter()
const events = ref([])
const loading = ref(true)
const error = ref('')
const query = ref('')
const fromDate = ref('')
const toDate = ref('')
const statusFilter = ref('')

const dateRangeInvalid = computed(
  () => Boolean(fromDate.value && toDate.value && fromDate.value > toDate.value),
)
const filtersActive = computed(
  () => Boolean(query.value.trim() || fromDate.value || toDate.value || statusFilter.value),
)

const narrowed = computed(() => {
  const term = query.value.trim().toLowerCase()
  return events.value.filter((event) => {
    if (term && !(event.eventName || '').toLowerCase().includes(term)) return false
    if (dateRangeInvalid.value || (!fromDate.value && !toDate.value)) return true
    const day = startDay(event.proposedStartAt)
    if (!day) return false
    if (fromDate.value && day < fromDate.value) return false
    if (toDate.value && day > toDate.value) return false
    return true
  })
})

const flags = computed(() => {
  const counts = new Map(events.value.map((event) => [event.status, 0]))
  for (const event of narrowed.value) {
    counts.set(event.status, (counts.get(event.status) || 0) + 1)
  }
  return [...counts.entries()]
    .map(([status, count]) => ({ status, count }))
    .sort((a, b) => statusRank(a.status) - statusRank(b.status) || a.status.localeCompare(b.status))
})

const visible = computed(() => {
  if (!statusFilter.value) return narrowed.value
  return narrowed.value.filter((event) => event.status === statusFilter.value)
})

function statusRank(status) {
  const index = STATUS_ORDER.indexOf(status)
  return index === -1 ? STATUS_ORDER.length : index
}

function statusLabel(status) {
  return String(status || 'Unknown')
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function startDay(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

function formatRange(start, end) {
  if (!start && !end) return 'No date set yet'
  if (!start || !end) return 'Date incomplete'
  return `${new Date(start).toLocaleString()} – ${new Date(end).toLocaleString()}`
}

function toggleStatus(status) {
  statusFilter.value = statusFilter.value === status ? '' : status
}

function clearFilters() {
  query.value = ''
  fromDate.value = ''
  toDate.value = ''
  statusFilter.value = ''
}

function open(eventId) {
  router.push(`/app/events/${eventId}`)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getEvents()
    events.value = data
      .filter((event) => event.coordinatorId && event.coordinatorId === session.userId)
      .filter((event) => event.status !== 'draft' && event.status !== 'discarded')
      .sort((a, b) => new Date(a.proposedStartAt || 0) - new Date(b.proposedStartAt || 0))
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load assigned events. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.assigned-events { display: flex; flex-direction: column; gap: 12px; max-width: 860px; }
.empty-note { font-size: 14px; color: var(--muted); margin: 0; }
.hint { margin: 0; font-size: 13px; color: #ffc66d; }
.form-error {
  color: #ff8a76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
}
.toolbar label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
}
.search { flex: 1; min-width: 220px; }
.toolbar input {
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: 10px;
  color: var(--text);
  font: inherit;
  font-size: 14px;
  letter-spacing: 0;
  text-transform: none;
  padding: 9px 12px;
  color-scheme: dark;
}
.toolbar input:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .5);
}
.clear { padding: 9px 8px; }

.flags { display: flex; flex-wrap: wrap; gap: 8px; }
.flag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--glass);
  border: 1px solid var(--hairline);
  color: var(--body);
  border-radius: 999px;
  padding: 6px 12px;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.flag span {
  min-width: 18px;
  text-align: center;
  font-size: 12px;
  color: var(--halo);
  background: rgba(124, 77, 255, .2);
  border-radius: 999px;
  padding: 1px 6px;
}
.flag.active {
  color: var(--text);
  border-color: rgba(167, 139, 250, .55);
  background: rgba(124, 77, 255, .16);
}
.flag.empty { opacity: .55; }

.event-card {
  text-align: left;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 18px 20px;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.event-card:hover { border-color: rgba(167, 139, 250, .35); background: var(--glass-strong); }
.event-name { font-size: 16px; font-weight: 500; color: var(--text); margin-bottom: 6px; }
.event-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
.status-pill {
  font-size: 11px;
  letter-spacing: .05em;
  text-transform: uppercase;
  color: var(--halo);
  background: rgba(124, 77, 255, .18);
  border: 1px solid rgba(167, 139, 250, .3);
  border-radius: 999px;
  padding: 2px 8px;
}
</style>
