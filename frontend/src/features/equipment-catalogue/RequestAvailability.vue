<template>
  <div class="request-check">
    <p v-if="loading" class="empty">Loading equipment requests…</p>
    <p v-else-if="error" class="empty error">{{ error }}</p>
    <p v-else-if="!groups.length" class="empty">No equipment requests yet.</p>
    <article v-for="group in groups" :key="group.eventId" class="event-card">
      <div class="event-header">
        <h3>Event {{ group.eventId }}</h3>
        <button type="button" class="btn btn-ghost small" @click="check(group.eventId)">Check availability</button>
      </div>
      <p v-if="results[group.eventId]" class="verdict" :class="{ short: !results[group.eventId].canMeet }">
        {{ results[group.eventId].canMeet ? 'This request can be met.' : 'This request cannot be met.' }}
        Checking does not reserve anything.
      </p>
      <table v-if="results[group.eventId]" class="lines">
        <thead>
          <tr>
            <th>Equipment</th>
            <th>Requested</th>
            <th>Available</th>
            <th>Shortfall</th>
            <th>Held by</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(line, index) in results[group.eventId].lines" :key="`${line.equipmentId}-${index}`">
            <td>{{ line.name }}</td>
            <td>{{ line.requestedQuantity }}</td>
            <td>{{ line.availableQuantity }}</td>
            <td>{{ line.shortfall }}</td>
            <td>{{ heldBy(line) }}</td>
          </tr>
        </tbody>
      </table>
      <ul class="request-list">
        <li v-for="request in group.requests" :key="request.requestId" class="request-row">
          <div class="request-main">
            <strong>{{ request.quantity }} × {{ equipmentName(request.equipmentId) }}</strong>
            <span class="status">{{ statusLabel(request.status) }}</span>
          </div>
          <p v-if="request.technicalRequirements" class="notes">{{ request.technicalRequirements }}</p>
          <p v-if="request.reviewedBy" class="meta">
            Updated by {{ request.reviewedBy }}
            <template v-if="request.reviewedAt"> at {{ formatWhen(request.reviewedAt) }}</template>
          </p>
          <p v-if="request.reviewNote" class="notes">{{ request.reviewNote }}</p>
          <p v-if="actionError[request.requestId]" class="error">{{ actionError[request.requestId] }}</p>
          <div v-if="request.status === 'pending' && decisionFor !== request.requestId" class="actions">
            <button type="button" class="btn btn-solid small" :disabled="busy === request.requestId" @click="accept(request)">Accept</button>
            <button type="button" class="btn btn-ghost small" :disabled="busy === request.requestId" @click="startDecision(request, 'reject')">Reject</button>
            <button type="button" class="btn btn-ghost small" :disabled="busy === request.requestId" @click="startDecision(request, 'unavailable')">Mark unavailable</button>
          </div>
          <div v-else-if="request.status === 'approved'" class="actions">
            <button type="button" class="btn btn-solid small" :disabled="busy === request.requestId" @click="reserve(request)">Reserve</button>
          </div>
          <form v-if="decisionFor === request.requestId" class="unavailable-form" @submit.prevent="confirmDecision(request)">
            <label>Reason<input v-model="decisionReason" required /></label>
            <label v-if="decisionKind === 'unavailable'">Note<input v-model="decisionNote" /></label>
            <div class="actions">
              <button type="button" class="btn btn-ghost small" @click="cancelDecision(request)">Cancel</button>
              <button type="submit" class="btn btn-solid small" :disabled="busy === request.requestId || !decisionReason.trim()">Save</button>
            </div>
          </form>
        </li>
      </ul>
    </article>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  checkEquipmentAvailability,
  getEquipmentList,
  getEquipmentRequests,
  markEquipmentRequestUnavailable,
  reserveEquipmentRequest,
  reviewEquipmentRequest,
} from '../../api/equipmentService.js'

const requests = ref([])
const names = ref({})
const results = ref({})
const loading = ref(true)
const error = ref('')
const actionError = ref({})
const busy = ref('')
const decisionFor = ref('')
const decisionKind = ref('')
const decisionReason = ref('')
const decisionNote = ref('')

const groups = computed(() => {
  const grouped = new Map()
  for (const request of requests.value) {
    if (request.status === 'cancelled') continue
    if (!grouped.has(request.eventId)) grouped.set(request.eventId, [])
    grouped.get(request.eventId).push(request)
  }
  return [...grouped.entries()].map(([eventId, rows]) => ({ eventId, requests: rows }))
})

function equipmentName(equipmentId) {
  return names.value[equipmentId] || equipmentId
}

function statusLabel(status) {
  if (status === 'pending') return 'Requested'
  if (status === 'approved') return 'Accepted'
  if (status === 'reserved') return 'Reserved'
  if (status === 'unavailable') return 'Unavailable'
  if (status === 'rejected') return 'Rejected'
  return status
}

function formatWhen(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function heldBy(line) {
  const conflicts = line.conflictingEvents || []
  if (!conflicts.length) return '—'
  return conflicts.map((item) => `${item.eventId} (${item.quantity})`).join(', ')
}

function detail(err, fallback) {
  const message = err.response?.data?.detail
  return typeof message === 'string' ? message : fallback
}

async function reload() {
  const { data } = await getEquipmentRequests()
  requests.value = data
}

async function run(request, action) {
  busy.value = request.requestId
  actionError.value = { ...actionError.value, [request.requestId]: '' }
  try {
    await action()
    await reload()
  } catch (err) {
    actionError.value = { ...actionError.value, [request.requestId]: detail(err, 'This action could not be saved.') }
  } finally {
    busy.value = ''
  }
}

function accept(request) {
  return run(request, () => reviewEquipmentRequest(request.requestId, { approve: true, reviewNote: 'Accepted' }))
}

function reserve(request) {
  return run(request, () => reserveEquipmentRequest(request.requestId))
}

function startDecision(request, kind) {
  decisionFor.value = request.requestId
  decisionKind.value = kind
  decisionReason.value = ''
  decisionNote.value = ''
  actionError.value = { ...actionError.value, [request.requestId]: '' }
}

function cancelDecision(request) {
  decisionFor.value = ''
  decisionKind.value = ''
  decisionReason.value = ''
  decisionNote.value = ''
  actionError.value = { ...actionError.value, [request.requestId]: '' }
}

function confirmDecision(request) {
  const reason = decisionReason.value.trim()
  if (!reason) {
    actionError.value = { ...actionError.value, [request.requestId]: 'A reason is required.' }
    return
  }
  const note = decisionNote.value.trim()
  const kind = decisionKind.value
  return run(request, async () => {
    if (kind === 'reject') {
      await reviewEquipmentRequest(request.requestId, { approve: false, reviewNote: reason })
    } else {
      await markEquipmentRequestUnavailable(request.requestId, { reason, note })
    }
    decisionFor.value = ''
  })
}

async function check(eventId) {
  error.value = ''
  try {
    const { data } = await checkEquipmentAvailability({ eventId })
    results.value = { ...results.value, [eventId]: data }
  } catch {
    error.value = 'Unable to check that request. Please try again.'
  }
}

onMounted(async () => {
  try {
    const [requestList, equipmentList] = await Promise.all([getEquipmentRequests(), getEquipmentList()])
    requests.value = requestList.data
    names.value = Object.fromEntries(equipmentList.data.map((item) => [item.equipmentId, item.name]))
  } catch {
    error.value = 'Unable to load equipment requests. Please try again.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.request-check { display: flex; flex-direction: column; gap: 14px; }
.event-card {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 16px;
  padding: 18px 20px;
}
.event-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
h3 { margin: 0; font-size: 16px; font-weight: 500; }
.verdict { margin: 12px 0 0; font-size: 14px; }
.verdict.short { color: #ffb4a8; }
.lines { width: 100%; margin-top: 12px; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 8px 10px 8px 0; border-bottom: 1px solid var(--hairline); }
.request-list { list-style: none; margin: 14px 0 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.request-row { border-top: 1px solid var(--hairline); padding-top: 12px; }
.request-main { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.status { font-size: 12px; color: var(--muted); }
.notes, .meta { margin: 6px 0 0; font-size: 13px; color: var(--muted); }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.unavailable-form { display: grid; gap: 8px; margin-top: 10px; }
.unavailable-form label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.unavailable-form input {
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: 10px;
  color: var(--text);
  font: inherit;
  font-size: 14px;
  padding: 8px 10px;
}
.empty { margin: 0; color: var(--muted); }
.error { color: #ffb4a8; font-size: 13px; }
</style>
