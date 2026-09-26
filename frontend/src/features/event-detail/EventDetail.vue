<template>
  <div class="event-detail">
    <p v-if="loading" class="empty-note">Loading event…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>

    <div v-else class="detail-card">
      <div class="detail-head">
        <div>
          <div class="event-name">{{ event.eventName }}</div>
          <span class="status-pill">{{ event.status }}</span>
        </div>
        <div class="actions">
          <button
            v-if="event.status === 'draft'"
            class="btn btn-outline"
            data-testid="event-discard"
            @click="openDiscardConfirm"
          >
            Discard
          </button>
        </div>
      </div>

      <dl class="detail-grid">
        <dt>When</dt>
        <dd>{{ formatRange(event.proposedStartAt, event.proposedEndAt) }}</dd>

        <dt>Expected attendance</dt>
        <dd>{{ event.expectedAttendance }}</dd>

        <dt v-if="event.purpose">Purpose</dt>
        <dd v-if="event.purpose">{{ event.purpose }}</dd>

        <dt v-if="event.description">Description</dt>
        <dd v-if="event.description">{{ event.description }}</dd>

        <dt v-if="event.venueRequirements">Venue requirements</dt>
        <dd v-if="event.venueRequirements">{{ event.venueRequirements }}</dd>

        <dt v-if="event.equipmentRequirements">Equipment requirements</dt>
        <dd v-if="event.equipmentRequirements">{{ event.equipmentRequirements }}</dd>
      </dl>

      <p v-if="discardError" class="form-error">{{ discardError }}</p>
    </div>

    <!-- Discard confirmation -->
    <div v-if="confirming" class="modal-backdrop" @click.self="confirming = false">
      <div class="modal" data-testid="discard-confirm">
        <h3>Discard this request?</h3>
        <p>
          <strong>{{ event.eventName }}</strong> will be discarded. This can't be undone, but you can
          always start a new request.
        </p>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="confirming = false">Cancel</button>
          <button class="btn btn-solid" :disabled="discarding" @click="confirmDiscard">
            {{ discarding ? 'Discarding…' : 'Discard request' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getEvent, discardEvent } from '../../api/eventService.js'

const route = useRoute()
const router = useRouter()

const event = ref(null)
const loading = ref(true)
const error = ref('')

const confirming = ref(false)
const discarding = ref(false)
const discardError = ref('')

function formatRange(start, end) {
  if (!start && !end) return 'No date set yet'
  if (!start || !end) return 'Date incomplete'
  return `${new Date(start).toLocaleString()} – ${new Date(end).toLocaleString()}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getEvent(route.params.id)
    event.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load this event. Please try again.'
  } finally {
    loading.value = false
  }
}

function openDiscardConfirm() {
  discardError.value = ''
  confirming.value = true
}

async function confirmDiscard() {
  discarding.value = true
  discardError.value = ''
  try {
    await discardEvent(event.value.eventId)
    confirming.value = false
    router.push({ path: '/app', query: { tab: 'My Events' } })
  } catch (err) {
    discardError.value = err.response?.data?.detail || 'Could not discard this request. Please try again.'
    confirming.value = false
  } finally {
    discarding.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.event-detail { max-width: 620px; }

.empty-note { font-size: 14px; color: var(--muted); }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
}

.detail-card {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 24px 26px;
}
.detail-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 18px; }
.event-name { font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 18px; margin-bottom: 8px; }

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

.detail-grid { display: grid; grid-template-columns: 180px 1fr; row-gap: 12px; column-gap: 16px; }
.detail-grid dt {
  font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
  color: var(--muted);
}
.detail-grid dd { margin: 0; font-size: 14px; color: var(--body); line-height: 1.6; }

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
.modal h3 { margin: 0 0 14px; font-size: 18px; font-weight: 500; }
.modal p { font-size: 14px; line-height: 1.7; color: var(--body); margin: 0 0 6px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }

.btn:disabled { opacity: .55; cursor: progress; }

@media (max-width: 560px) {
  .detail-head { flex-direction: column; }
  .detail-grid { grid-template-columns: 1fr; }
}
</style>
