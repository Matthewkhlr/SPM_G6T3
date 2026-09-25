<template>
  <div class="review-queue">
    <p v-if="loading" class="empty-note">Loading submitted events…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="!events.length" class="empty-note">No events are awaiting review.</p>

    <div v-for="event in events" :key="event.eventId" class="event-card">
      <div class="event-head">
        <div>
          <div class="event-name">{{ event.eventName }}</div>
          <div class="event-meta">
            {{ formatRange(event.proposedStartAt, event.proposedEndAt) }} ·
            <span class="status-pill">{{ event.status }}</span>
            <span v-if="event.submittedAt" class="waiting-note">· waiting {{ waitingFor(event.submittedAt) }}</span>
          </div>
        </div>
        <div class="actions">
          <button
            class="btn btn-solid"
            :disabled="isBusy(event.eventId)"
            @click="approve(event)"
          >
            Approve
          </button>
          <button
            class="btn btn-outline"
            :disabled="isBusy(event.eventId)"
            @click="openReject(event)"
          >
            Reject
          </button>
        </div>
      </div>
      <p v-if="rowErrors[event.eventId]" class="row-error">{{ rowErrors[event.eventId] }}</p>
    </div>

    <!-- Reject reason modal -->
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
import { onMounted, reactive, ref } from 'vue'
import { getSubmissionQueue, approveEvent, rejectEvent } from '../../api/eventService.js'

const events = ref([])
const loading = ref(true)
const error = ref('')
const busyIds = reactive(new Set())
const rowErrors = reactive({})

const rejecting = ref(null)
const rejectReason = ref('')

function isBusy(eventId) {
  return busyIds.has(eventId)
}

function formatRange(start, end) {
  const startDate = new Date(start)
  const endDate = new Date(end)
  return `${startDate.toLocaleString()} – ${endDate.toLocaleString()}`
}

function waitingFor(submittedAt) {
  const ms = Date.now() - new Date(submittedAt).getTime()
  const hours = Math.floor(ms / (1000 * 60 * 60))
  if (hours < 1) return 'less than an hour'
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  return `${days}d ${hours % 24}h`
}

async function loadEvents() {
  loading.value = true
  error.value = ''
  try {
    // Server already filters to status "submitted" and orders by
    // submittedAt ascending (longest-waiting first) - no client-side
    // filtering/sorting needed here.
    const { data } = await getSubmissionQueue()
    events.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load the review queue. Please try again.'
  } finally {
    loading.value = false
  }
}

function removeFromQueue(eventId) {
  events.value = events.value.filter((event) => event.eventId !== eventId)
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

onMounted(loadEvents)
</script>

<style scoped>
.review-queue { display: flex; flex-direction: column; gap: 12px; max-width: 720px; }

.empty-note { font-size: 14px; color: var(--muted); }

.event-card {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 18px 20px;
  transition: border-color .4s var(--ease-out), background .4s var(--ease-out);
}
.event-card:hover { border-color: rgba(167, 139, 250, .3); background: var(--glass-strong); }
.event-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.event-name { font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 15px; }
.event-meta { font-size: 12px; margin-top: 4px; color: var(--muted); display: flex; align-items: center; gap: 8px; }
.waiting-note { color: var(--muted); }

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

@media (max-width: 560px) {
  .event-head { flex-direction: column; align-items: flex-start; }
}
</style>
