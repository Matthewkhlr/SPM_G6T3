<template>
  <div class="review-queue">
    <div v-if="!loading && !error" class="queue-filters">
      <button
        class="filter-btn"
        :class="{ active: filter === 'unassigned' }"
        data-testid="queue-filter-unassigned"
        @click="toggleFilter('unassigned')"
      >
        Unassigned only
      </button>
      <button
        class="filter-btn"
        :class="{ active: filter === 'mine' }"
        data-testid="queue-filter-mine"
        @click="toggleFilter('mine')"
      >
        My assignments
      </button>
      <button
        class="filter-btn sort-btn"
        :class="{ active: sortMode === 'proposedStartAt' }"
        @click="toggleSort"
      >
        {{ sortMode === 'proposedStartAt' ? 'Sorted by event date' : 'Sort by event date' }}
      </button>
    </div>

    <p v-if="loading" class="empty-note">Loading submitted events…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="!filteredEvents.length" data-testid="review-queue-empty" class="empty-note">
      {{ emptyMessage }}
    </p>

    <div
      v-for="event in filteredEvents"
      :key="event.eventId"
      class="event-card"
      :data-testid="`review-queue-${event.eventId}`"
      :data-assigned="String(!!event.coordinatorId)"
      role="button"
      tabindex="0"
      @click="openDetails(event)"
      @keydown.enter="openDetails(event)"
    >
      <div class="event-head">
        <div class="event-main">
          <div class="event-name-row">
            <span class="event-name">{{ event.eventName }}</span>
            <span v-if="event.dateNear" class="near-flag">Date is near</span>
          </div>
          <div v-if="event.organisationName" class="event-org">{{ event.organisationName }}</div>
          <div class="event-meta">
            <span data-testid="queue-datetime">
              {{ formatLocal(event.proposedStartAt) }} – {{ formatLocal(event.proposedEndAt) }}
            </span>
            <span data-testid="queue-attendance">{{ event.expectedAttendance }} attendees</span>
            <span data-testid="queue-status" class="status-pill">{{ event.status }}</span>
            <span data-testid="queue-submitted-at">
              Submitted {{ formatSubmitted(event.submittedAt) }} · waiting {{ waitingFor(event.submittedAt) }}
            </span>
          </div>
          <div class="event-assignee">{{ event.coordinatorId ? 'Assigned' : 'Unassigned' }}</div>
        </div>
        <div class="actions">
          <button
            class="btn btn-solid"
            :disabled="isBusy(event.eventId)"
            @click.stop="approve(event)"
          >
            Approve
          </button>
          <button
            class="btn btn-outline"
            :disabled="isBusy(event.eventId)"
            @click.stop="openReject(event)"
          >
            Reject
          </button>
        </div>
      </div>
      <p v-if="rowErrors[event.eventId]" class="row-error">{{ rowErrors[event.eventId] }}</p>
    </div>

    <!-- Event details popup -->
    <div v-if="selected" class="modal-backdrop" @click.self="closeDetails">
      <div class="modal details-modal" role="dialog" aria-modal="true">
        <div class="details-head">
          <div>
            <h3>{{ selected.eventName }}</h3>
            <span class="status-pill">{{ selected.status }}</span>
          </div>
          <button class="close-btn" aria-label="Close" @click="closeDetails">×</button>
        </div>

        <div class="details-body">
          <dl>
            <div v-for="row in detailRows(selected)" :key="row.label" class="detail-row">
              <dt>{{ row.label }}</dt>
              <dd :class="{ empty: row.empty }">{{ row.value }}</dd>
            </div>
          </dl>
        </div>

        <p v-if="rowErrors[selected.eventId]" class="row-error">{{ rowErrors[selected.eventId] }}</p>

        <div class="details-actions">
          <button
            class="btn btn-outline"
            :disabled="isBusy(selected.eventId)"
            data-testid="queue-assign-coordinator"
            @click="assigning = selected"
          >
            {{ selected.coordinatorId ? 'Change coordinator' : 'Assign coordinator' }}
          </button>
          <button class="btn btn-outline" :disabled="isBusy(selected.eventId)" @click="openReject(selected)">
            Reject
          </button>
          <button class="btn btn-solid" :disabled="isBusy(selected.eventId)" @click="approve(selected)">
            Approve
          </button>
        </div>
      </div>
    </div>

    <!-- SPM-66: assign from the queue (stacks above the details popup) -->
    <AssignCoordinatorDialog
      v-if="assigning"
      :event="assigning"
      @close="assigning = null"
      @assigned="onAssigned"
    />

    <!-- Reject reason modal (stacks above the details popup when opened from it) -->
    <div v-if="rejecting" class="modal-backdrop" @click.self="rejecting = null">
      <div class="modal">
        <h3>Reject {{ rejecting.eventName }}</h3>
        <label>Reason (optional)</label>
        <textarea v-model="rejectReason" rows="3" placeholder="Let the organiser know why"></textarea>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="rejecting = null">Cancel</button>
          <button class="btn btn-solid" :disabled="isBusy(rejecting.eventId)" @click="confirmReject">
            Reject event
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { getSubmissionQueue, approveEvent, rejectEvent } from '../../api/eventService.js'
import { getMe } from '../../api/userService.js'
import AssignCoordinatorDialog from '../event-detail/AssignCoordinatorDialog.vue'

const events = ref([])
const loading = ref(true)
const error = ref('')
const busyIds = reactive(new Set())
const rowErrors = reactive({})

const selected = ref(null)
const rejecting = ref(null)
const rejectReason = ref('')
const assigning = ref(null)

// 'all' | 'unassigned' | 'mine'
const filter = ref('all')
// 'waiting' (default, server-side longest-wait-first) | 'proposedStartAt'
const sortMode = ref('waiting')
const myUserId = ref(null)

// Ticks once a minute so the "waiting" times stay current without a reload.
const now = ref(Date.now())
let ticker = null

function isBusy(eventId) {
  return busyIds.has(eventId)
}

// submittedAt is stamped with utcnow() on the server and serialised without a
// timezone marker, and new Date() reads a marker-less string as *local* time -
// which made every request look hours older than it was. Treat it as UTC.
// (Proposed start/end are different: they come from local datetime-local
// inputs, so they are intentionally left as local time.)
function parseUtc(value) {
  if (!value) return null
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(value)
  return new Date(hasZone ? value : `${value}Z`)
}

function waitingFor(submittedAt) {
  const start = parseUtc(submittedAt)
  if (!start) return 'unknown'
  const minutes = Math.max(0, Math.floor((now.value - start.getTime()) / 60000))
  if (minutes < 1) return 'under a minute'
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ${minutes % 60}m`
  const days = Math.floor(hours / 24)
  return `${days}d ${hours % 24}h`
}

function formatLocal(value) {
  return value ? new Date(value).toLocaleString() : ''
}

function formatSubmitted(value) {
  const date = parseUtc(value)
  return date ? date.toLocaleString() : ''
}

const filteredEvents = computed(() => {
  if (filter.value === 'unassigned') return events.value.filter((event) => !event.coordinatorId)
  if (filter.value === 'mine') {
    return events.value.filter((event) => event.coordinatorId && event.coordinatorId === myUserId.value)
  }
  return events.value
})

const emptyMessage = computed(() => {
  if (filter.value === 'unassigned') return 'No unassigned requests match this filter.'
  if (filter.value === 'mine') return 'No requests are currently assigned to you.'
  return 'No requests are awaiting review.'
})

function toggleFilter(mode) {
  filter.value = filter.value === mode ? 'all' : mode
}

async function toggleSort() {
  sortMode.value = sortMode.value === 'proposedStartAt' ? 'waiting' : 'proposedStartAt'
  await loadEvents()
}

function detailRows(event) {
  const rows = [
    { label: 'Organisation', value: event.organisationName },
    { label: 'Submitted', value: formatSubmitted(event.submittedAt) },
    { label: 'Waiting', value: waitingFor(event.submittedAt) },
    { label: 'Assigned coordinator', value: event.coordinatorId },
    { label: 'Category', value: event.category },
    { label: 'Proposed start', value: formatLocal(event.proposedStartAt) },
    { label: 'Proposed end', value: formatLocal(event.proposedEndAt) },
    { label: 'Expected attendance', value: event.expectedAttendance != null ? String(event.expectedAttendance) : '' },
    { label: 'Purpose', value: event.purpose },
    { label: 'Description', value: event.description },
    { label: 'Venue requirements', value: event.venueRequirements },
    { label: 'Equipment requirements', value: event.equipmentRequirements },
    { label: 'Accessibility needs', value: event.accessibilityNeeds },
    { label: 'Layout preference', value: event.layoutPreference },
    { label: 'Registration', value: event.registrationEnabled ? 'Enabled' : 'Not enabled' },
  ]
  if (event.registrationEnabled) {
    rows.push(
      { label: 'Registration opens', value: formatLocal(event.registrationOpensAt) },
      { label: 'Registration closes', value: formatLocal(event.registrationClosesAt) },
      { label: 'Capacity', value: event.capacity != null ? String(event.capacity) : '' },
    )
  }
  return rows.map((row) => ({
    ...row,
    empty: !row.value,
    value: row.value || 'Not provided',
  }))
}

function openDetails(event) {
  selected.value = event
}

function closeDetails() {
  selected.value = null
}

async function loadEvents() {
  loading.value = true
  error.value = ''
  try {
    // Server filters to submitted/under review/changes requested and orders
    // by submittedAt ascending (longest-waiting first) by default, or by
    // proposedStartAt when sortMode is 'proposedStartAt'. "mine"/"unassigned"
    // are applied client-side below (filteredEvents) against this list.
    const { data } = await getSubmissionQueue({
      sort: sortMode.value === 'proposedStartAt' ? 'proposedStartAt' : undefined,
    })
    events.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load the review queue. Please try again.'
  } finally {
    loading.value = false
  }
}

async function loadMyUserId() {
  try {
    const { data } = await getMe()
    myUserId.value = data.userId
  } catch {
    // Non-fatal - the "mine" filter just won't match anything.
  }
}

function removeFromQueue(eventId) {
  events.value = events.value.filter((event) => event.eventId !== eventId)
  if (selected.value?.eventId === eventId) selected.value = null
}

async function approve(event) {
  busyIds.add(event.eventId)
  delete rowErrors[event.eventId]
  try {
    await approveEvent(event.eventId)
    removeFromQueue(event.eventId)
  } catch (err) {
    rowErrors[event.eventId] = err.response?.data?.detail || 'Could not approve this event.'
  } finally {
    busyIds.delete(event.eventId)
  }
}

// Assigning moves a submitted request to "under review" and sets its
// coordinator, so reload the queue and keep the open popup in step.
async function onAssigned(assignment) {
  assigning.value = null
  await loadEvents()
  if (selected.value?.eventId === assignment.eventId) {
    selected.value = events.value.find((event) => event.eventId === assignment.eventId) || null
  }
}

function openReject(event) {
  rejecting.value = event
  rejectReason.value = ''
}

async function confirmReject() {
  const event = rejecting.value
  busyIds.add(event.eventId)
  delete rowErrors[event.eventId]
  try {
    await rejectEvent(event.eventId, rejectReason.value)
    removeFromQueue(event.eventId)
    rejecting.value = null
  } catch (err) {
    rowErrors[event.eventId] = err.response?.data?.detail || 'Could not reject this event.'
    rejecting.value = null
  } finally {
    busyIds.delete(event.eventId)
  }
}

onMounted(() => {
  loadEvents()
  loadMyUserId()
  ticker = setInterval(() => { now.value = Date.now() }, 60000)
})
onUnmounted(() => clearInterval(ticker))
</script>

<style scoped>
.review-queue { display: flex; flex-direction: column; gap: 12px; max-width: 720px; }

.queue-filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 4px; }
.filter-btn {
  background: var(--glass);
  border: 1px solid var(--hairline);
  color: var(--muted);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 12px;
  cursor: pointer;
  transition: border-color .3s var(--ease-out), color .3s var(--ease-out), background .3s var(--ease-out);
}
.filter-btn:hover { border-color: rgba(167, 139, 250, .4); color: var(--text); }
.filter-btn.active {
  color: var(--text);
  border-color: rgba(167, 139, 250, .6);
  background: rgba(124, 77, 255, .18);
}
.sort-btn { margin-left: auto; }

.empty-note { font-size: 14px; color: var(--muted); }

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
.event-card:focus-visible { outline: none; border-color: rgba(167, 139, 250, .6); box-shadow: 0 0 0 3px rgba(124, 77, 255, .16); }
.event-card:hover { border-color: rgba(167, 139, 250, .3); background: var(--glass-strong); }
.event-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.event-main { min-width: 0; }
.event-name-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.event-name { font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 15px; }
.event-org { font-size: 12px; color: var(--muted); margin-top: 2px; }
.event-meta { font-size: 12px; margin-top: 6px; color: var(--muted); display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.event-assignee { font-size: 11px; color: var(--muted); margin-top: 6px; text-transform: uppercase; letter-spacing: .06em; }

.near-flag {
  font-size: 10px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #FF8A76;
  background: rgba(255, 138, 118, .12);
  border: 1px solid rgba(255, 138, 118, .3);
  border-radius: 999px;
  padding: 2px 8px;
}

.actions { display: flex; gap: 10px; flex-shrink: 0; }

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

.row-error { color: #FF8A76; font-size: 12px; margin: 10px 0 0; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
}

.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(5, 2, 14, .7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center; z-index: 10;
}
.modal {
  background: linear-gradient(160deg, #1A0C3B, #0D0524);
  border: 1px solid rgba(167, 139, 250, .28);
  box-shadow: 0 30px 90px rgba(4, 1, 12, .7), 0 0 60px rgba(124, 77, 255, .18);
  border-radius: 18px;
  padding: 30px;
  width: 360px;
}
.modal h3 { margin: 0 0 20px; font-size: 18px; font-weight: 500; }
.modal label {
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); display: block; margin-bottom: 6px;
}
.modal textarea {
  width: 100%;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  padding: 11px 12px;
  font-size: 14px;
  color: var(--text);
  font-family: 'Inter', sans-serif;
  resize: vertical;
  line-height: 1.6;
}
.modal textarea:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .6);
  box-shadow: 0 0 0 3px rgba(124, 77, 255, .16);
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }

.btn:disabled { opacity: .55; cursor: progress; }

/* Details popup */
.details-modal {
  width: 580px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  padding: 26px 28px;
}
.details-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 18px; }
.details-head h3 { margin: 0 0 8px; }
.close-btn {
  background: none; border: 1px solid var(--hairline); color: var(--body);
  width: 32px; height: 32px; border-radius: 50%; font-size: 18px; line-height: 1;
  cursor: pointer; flex-shrink: 0;
}
.close-btn:hover { background: rgba(167, 139, 250, .1); color: var(--text); }
.details-body { overflow-y: auto; padding-right: 6px; }
.detail-row {
  display: grid;
  grid-template-columns: 150px 1fr;
  gap: 4px 16px;
  padding: 10px 0;
  border-top: 1px solid var(--hairline);
}
.detail-row:first-child { border-top: none; }
.detail-row dt {
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); padding-top: 2px;
}
.detail-row dd { margin: 0; font-size: 14px; color: var(--text); line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.detail-row dd.empty { color: var(--muted); font-style: italic; }
.details-body dl { margin: 0; }
.details-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--hairline); }

@media (max-width: 560px) {
  .event-head { flex-direction: column; align-items: flex-start; }
  .detail-row { grid-template-columns: 1fr; }
  .sort-btn { margin-left: 0; }
}
</style>
