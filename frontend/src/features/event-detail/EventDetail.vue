<template>
  <div class="event-page">
    <button type="button" class="btn btn-ghost back" @click="goBack">
      ← {{ backTarget.label }}
    </button>

    <p v-if="loading" class="empty-note">Loading event…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>

    <template v-else>
      <header class="page-head">
        <div>
          <p class="eyebrow">Event</p>
          <h1>{{ event.eventName }}</h1>
          <span class="status-pill">{{ event.status }}</span>
        </div>
        <div class="actions">
          <button
            v-if="session.role === 'coordinator' && event.status !== 'draft'"
            class="btn btn-outline"
            data-testid="event-choose-venue"
            @click="router.push(`/app/events/${event.eventId}/venues`)"
          >
            Choose a venue
          </button>
          <button
            v-if="event.status === 'draft'"
            class="btn btn-outline"
            data-testid="event-discard"
            @click="openDiscardConfirm"
          >
            Discard
          </button>
        </div>
      </header>

      <div class="layout" :class="{ split: showEquipment }">
        <section class="panel">
          <h2>Details</h2>
          <dl class="facts">
            <div>
              <dt>When</dt>
              <dd>{{ formatRange(event.proposedStartAt, event.proposedEndAt) }}</dd>
            </div>
            <div>
              <dt>Expected attendance</dt>
              <dd>{{ event.expectedAttendance }}</dd>
            </div>
            <div v-if="event.purpose" class="wide">
              <dt>Purpose</dt>
              <dd>{{ event.purpose }}</dd>
            </div>
            <div v-if="event.description" class="wide">
              <dt>Description</dt>
              <dd>{{ event.description }}</dd>
            </div>
            <div v-if="event.venueRequirements" class="wide">
              <dt>Venue requirements</dt>
              <dd>{{ event.venueRequirements }}</dd>
            </div>
            <div v-if="event.equipmentRequirements" class="wide">
              <dt>Equipment notes</dt>
              <dd>{{ event.equipmentRequirements }}</dd>
            </div>
          </dl>
        </section>

        <EventEquipment v-if="showEquipment" :event="event" />
      </div>

      <p v-if="discardError" class="form-error">{{ discardError }}</p>
    </template>

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
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getEvent, discardEvent } from '../../api/eventService.js'
import { session } from '../../store/session.js'
import EventEquipment from './EventEquipment.vue'

const route = useRoute()
const router = useRouter()

const event = ref(null)
const loading = ref(true)
const error = ref('')

const confirming = ref(false)
const discarding = ref(false)
const discardError = ref('')

const showEquipment = computed(
  () => session.role === 'coordinator' || session.role === 'techsupport',
)
const backTarget = computed(() => {
  if (session.role === 'coordinator') return { label: 'Assigned Events', tab: 'Assigned Events' }
  if (session.role === 'organiser') return { label: 'My Events', tab: 'My Events' }
  if (session.role === 'techsupport') return { label: 'Upcoming Events', tab: 'Upcoming Events' }
  return { label: 'Dashboard', tab: 'Dashboard' }
})

function goBack() {
  router.push({ path: '/app', query: { tab: backTarget.value.tab } })
}

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
  margin: 6px 0 10px;
  font-size: 28px;
  font-weight: 500;
  letter-spacing: -.02em;
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

.layout { display: grid; gap: 18px; }
.layout.split { grid-template-columns: minmax(280px, 0.9fr) minmax(340px, 1.1fr); align-items: start; }

.panel {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 22px 24px;
}
.panel h2 { margin: 0 0 16px; font-size: 16px; font-weight: 500; }

.facts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px 20px; margin: 0; }
.facts .wide { grid-column: 1 / -1; }
.facts dt {
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 4px;
}
.facts dd { margin: 0; font-size: 14px; color: var(--body); line-height: 1.55; }

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

@media (max-width: 860px) {
  .event-page { padding: 22px 18px 36px; }
  .page-head, .layout.split { display: flex; flex-direction: column; align-items: stretch; }
  .facts { grid-template-columns: 1fr; }
  .back { margin-left: 0; }
}
</style>
