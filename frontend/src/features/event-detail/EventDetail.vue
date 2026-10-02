<template>
  <div class="event-page">
    <!-- While a dialog is open the page behind it is inert and hidden from
         assistive tech, so focus and screen readers stay in the dialog. -->
    <div :inert="dialogOpen || null" :aria-hidden="dialogOpen ? 'true' : null">
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
            <span
              class="status-pill"
              :class="{ attention: event.status === 'reconsidering' }"
              :data-testid="session.role === 'organiser' ? 'organiser-event-status' : 'event-status'"
            >
              {{ eventStatusLabel(event.status) }}
            </span>
          </div>
          <div class="actions">
            <button
              v-if="canApprove"
              class="btn btn-solid"
              data-testid="event-approve"
              @click="openApprove"
            >
              Approve request
            </button>
            <button
              v-if="canAssign"
              class="btn btn-outline"
              data-testid="assign-coordinator"
              @click="openAssign"
            >
              {{ event.coordinatorId ? 'Change coordinator' : 'Assign coordinator' }}
            </button>
            <button
              v-if="canEdit"
              class="btn btn-outline"
              data-testid="event-edit"
              @click="openEdit"
            >
              Edit event
            </button>
            <button
              v-if="canSetUpRegistration"
              class="btn btn-outline"
              data-testid="event-registration-settings-link"
              @click="router.push(`/app/events/${event.eventId}/registration-settings`)"
            >
              Registration settings
            </button>
            <button
              v-if="canChooseVenue"
              class="btn btn-outline"
              data-testid="event-choose-venue"
              @click="router.push(`/app/events/${event.eventId}/venues`)"
            >
              Choose a venue
            </button>
            <button
              v-if="session.role === 'organiser' && event.status === 'draft'"
              class="btn btn-outline"
              data-testid="event-discard"
              @click="openDiscardConfirm"
            >
              Discard
            </button>
          </div>
        </header>

        <p v-if="event.status === 'reconsidering'" class="notice attention" data-testid="event-reconsidering">
          Some planning details changed after this event was confirmed, so its venue and equipment
          arrangements are being re-checked. It will show as confirmed again once they are re-verified.
        </p>
        <!-- SPM-69 AC3: the organiser sees the outcome and any note on their event. -->
        <div
          v-if="decision?.decision === 'approved'"
          class="notice"
          :data-testid="session.role === 'organiser' ? 'organiser-decision' : 'event-decision'"
        >
          <p>
            <strong>Approved</strong><template v-if="decidedByName"> by {{ decidedByName }}</template>
            on {{ formatUtc(decision.decidedAt) }}. ConnectSphere has taken this event on and planning has started.
          </p>
          <p v-if="decision.decisionNote">
            {{ session.role === 'organiser' ? 'Note from your coordinator' : 'Note to the organiser' }}:
            {{ decision.decisionNote }}
          </p>
          <p v-if="event.status === 'planning'">Venue and equipment are still being arranged.</p>
        </div>
        <p v-if="savedNote" class="notice" data-testid="event-edit-saved">{{ savedNote }}</p>

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
              <div
                v-if="coordinator"
                class="wide"
                :data-testid="session.role === 'organiser' ? 'organiser-coordinator' : 'event-coordinator'"
              >
                <dt>Coordinator</dt>
                <dd v-if="coordinator.coordinatorId">
                  {{ coordinator.name || coordinator.coordinatorId }}
                  <template v-if="coordinator.email">
                    · <a :href="`mailto:${coordinator.email}`">{{ coordinator.email }}</a>
                  </template>
                </dd>
                <dd v-else class="muted">Not assigned yet</dd>
              </div>
              <!-- SPM-90 AC6: the organiser sees the registration settings for their event. -->
              <div
                class="wide"
                :data-testid="session.role === 'organiser' ? 'organiser-registration-settings' : 'event-registration-settings'"
              >
                <dt>Registration</dt>
                <dd v-if="event.registrationEnabled">
                  Needed · capacity {{ event.capacity }} · {{ registrationPeriod }}
                </dd>
                <dd v-else class="muted">Not needed</dd>
              </div>
              <div v-if="event.layoutPreference">
                <dt>Layout</dt>
                <dd>{{ event.layoutPreference }}</dd>
              </div>
              <div v-if="event.category">
                <dt>Category</dt>
                <dd>{{ event.category }}</dd>
              </div>
              <div v-if="event.organiserContact" class="wide">
                <dt>Organiser contact</dt>
                <dd>{{ event.organiserContact }}</dd>
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
              <div v-if="event.accessibilityNeeds" class="wide">
                <dt>Accessibility needs</dt>
                <dd>{{ event.accessibilityNeeds }}</dd>
              </div>
              <div v-if="event.equipmentRequirements" class="wide">
                <dt>Equipment notes</dt>
                <dd>{{ event.equipmentRequirements }}</dd>
              </div>
              <div v-if="internalNotes" class="wide">
                <dt>Internal notes (staff only)</dt>
                <dd>{{ internalNotes }}</dd>
              </div>
            </dl>
          </section>

          <EventEquipment v-if="showEquipment" :event="event" />
        </div>

        <EventChangeRequests
          v-if="CONTACT_ROLES.includes(session.role)"
          :event="event"
          @changed="reloadEvent"
        />

        <EventClarifications
          v-if="CONTACT_ROLES.includes(session.role)"
          :event="event"
          @changed="reloadEvent"
        />

        <p v-if="discardError" class="form-error">{{ discardError }}</p>
      </template>
    </div>

    <AssignCoordinatorDialog
      v-if="assigning"
      :event="event"
      @close="assigning = false"
      @assigned="onAssigned"
    />

    <ApproveEventDialog
      v-if="approving"
      :event="event"
      @close="approving = false"
      @approved="onApproved"
    />

    <EventEditForm
      v-if="editing"
      :event="event"
      :internal-notes="internalNotes"
      @close="editing = false"
      @saved="onSaved"
    />

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
import {
  getEvent,
  discardEvent,
  getEventCoordinator,
  getEventDecision,
  getInternalNotes,
} from '../../api/eventService.js'
import {
  IN_REVIEW_EVENT_STATUSES,
  LOCKED_EVENT_STATUSES,
  REGISTRATION_SETUP_STATUSES,
  eventStatusLabel,
} from '../../config/eventStatus.js'
import { session } from '../../store/session.js'
import { formatUtc } from '../../utils/datetime.js'
import ApproveEventDialog from './ApproveEventDialog.vue'
import AssignCoordinatorDialog from './AssignCoordinatorDialog.vue'
import EventChangeRequests from './EventChangeRequests.vue'
import EventClarifications from './EventClarifications.vue'
import EventEditForm from './EventEditForm.vue'
import EventEquipment from './EventEquipment.vue'

const route = useRoute()
const router = useRouter()

const event = ref(null)
const loading = ref(true)
const error = ref('')

const confirming = ref(false)
const discarding = ref(false)
const discardError = ref('')

const internalNotes = ref('')
const editing = ref(false)
const savedNote = ref('')

const coordinator = ref(null)
const assigning = ref(false)
const decision = ref(null)
const approving = ref(false)
const dialogOpen = computed(
  () => assigning.value || approving.value || editing.value || confirming.value,
)

// SPM-69 AC1/AC5: only the assigned coordinator, and only once the request is
// under review — so never while it is unassigned. The server enforces the same.
const canApprove = computed(
  () =>
    session.role === 'coordinator' &&
    !!event.value?.coordinatorId &&
    event.value.coordinatorId === session.userId &&
    IN_REVIEW_EVENT_STATUSES.includes(event.value.status),
)
// SPM-90 AC1: the assigned coordinator, from planning until confirmed.
const canSetUpRegistration = computed(
  () =>
    session.role === 'coordinator' &&
    !!event.value?.coordinatorId &&
    event.value.coordinatorId === session.userId &&
    REGISTRATION_SETUP_STATUSES.includes(event.value.status),
)
const registrationPeriod = computed(() => {
  const { registrationOpensAt: opens, registrationClosesAt: closes } = event.value || {}
  if (!opens && !closes) return 'period not set yet'
  const when = (value) => (value ? new Date(value).toLocaleString() : 'not set')
  return `opens ${when(opens)}, closes ${when(closes)}`
})
const decidedByName = computed(() =>
  coordinator.value?.coordinatorId && coordinator.value.coordinatorId === decision.value?.decidedBy
    ? coordinator.value.name
    : '',
)

// SPM-66: any coordinator can assign or reassign, but not a finished event or a draft.
const canAssign = computed(
  () => session.role === 'coordinator' && !LOCKED_EVENT_STATUSES.includes(event.value?.status),
)
// Who may see the coordinator's contact; the server enforces the organisation check.
const CONTACT_ROLES = ['organiser', 'coordinator', 'venue', 'techsupport']

// SPM-71: only the assigned coordinator edits, and never a finished event.
// The server enforces both; this only decides whether to offer the button.
const canEdit = computed(
  () =>
    session.role === 'coordinator' &&
    !!event.value?.coordinatorId &&
    event.value.coordinatorId === session.userId &&
    !LOCKED_EVENT_STATUSES.includes(event.value.status),
)

// SPM-46 AC1/AC2: requesting a venue is for the assigned coordinator only;
// every other internal user sees this page read-only. The server enforces it.
const canChooseVenue = computed(
  () =>
    session.role === 'coordinator' &&
    !!event.value?.coordinatorId &&
    event.value.coordinatorId === session.userId &&
    event.value.status !== 'draft',
)

const showEquipment = computed(
  () => session.role === 'coordinator' || session.role === 'techsupport',
)
const showRegistrations = computed(
  () =>
    !!event.value?.registrationEnabled &&
    (session.role === 'organiser' || session.role === 'coordinator'),
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
  if (event.value && session.role === 'coordinator') loadInternalNotes()
  if (event.value && CONTACT_ROLES.includes(session.role)) {
    loadCoordinator()
    loadDecision()
  }
}

// SPM-68: raising or resolving a clarification can change the status (and with
// it whether Approve warns), so re-read the event. Best effort.
async function reloadEvent() {
  try {
    const { data } = await getEvent(event.value.eventId)
    event.value = data
  } catch {
    // The page keeps showing what it had; the next load corrects it.
  }
}

// SPM-69 AC3: kept off the shared event read, so it is loaded like the coordinator. Best effort.
async function loadDecision() {
  try {
    const { data } = await getEventDecision(event.value.eventId)
    decision.value = data
  } catch {
    decision.value = null
  }
}

function openApprove() {
  savedNote.value = ''
  approving.value = true
}

function onApproved(approved) {
  approving.value = false
  event.value = approved
  decision.value = {
    decision: approved.decision,
    decisionNote: approved.decisionNote,
    decidedBy: approved.decidedBy,
    decidedAt: approved.decidedAt,
  }
  savedNote.value = 'Request approved. The organiser has been notified.'
}

// SPM-66 AC5: the organiser's one person to deal with. Best effort, like the notes.
async function loadCoordinator() {
  try {
    const { data } = await getEventCoordinator(event.value.eventId)
    coordinator.value = data
  } catch {
    coordinator.value = null
  }
}

function openAssign() {
  savedNote.value = ''
  assigning.value = true
}

async function onAssigned(assignment) {
  assigning.value = false
  // Assigning can change the status (Submitted → Under Review), so re-read the event.
  try {
    const { data } = await getEvent(assignment.eventId)
    event.value = data
  } catch {
    event.value = { ...event.value, coordinatorId: assignment.coordinatorId }
  }
  await loadCoordinator()
  savedNote.value = `Coordinator assigned: ${coordinator.value?.name || assignment.coordinatorId}.`
}

// Internal notes are coordinator-only and come from their own endpoint; if they
// can't be loaded the rest of the page still works.
async function loadInternalNotes() {
  try {
    const { data } = await getInternalNotes(event.value.eventId)
    internalNotes.value = data.internalNotes
  } catch {
    internalNotes.value = ''
  }
}

function openEdit() {
  savedNote.value = ''
  editing.value = true
}

function onSaved(updated) {
  event.value = updated
  internalNotes.value = updated.internalNotes || ''
  editing.value = false
  const flagged = updated.flaggedArrangements || []
  savedNote.value = flagged.length
    ? `Changes saved. Marked for re-verification: ${flagged.map((item) => item.summary).join('; ')}.`
    : 'Changes saved.'
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
.status-pill.attention {
  color: #FFD9A8;
  background: rgba(255, 170, 80, .14);
  border-color: rgba(255, 196, 120, .4);
}

.notice {
  font-size: 13px;
  line-height: 1.6;
  color: var(--halo);
  background: rgba(124, 77, 255, .1);
  border: 1px solid rgba(167, 139, 250, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 0 0 16px;
}
div.notice p { margin: 0; }
div.notice p + p { margin-top: 6px; }
.notice.attention {
  color: #FFD9A8;
  background: rgba(255, 170, 80, .08);
  border-color: rgba(255, 196, 120, .3);
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
.facts dd.muted { color: var(--muted); }
.facts dd a { color: var(--halo); }

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
