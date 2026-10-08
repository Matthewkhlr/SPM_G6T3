<template>
  <!-- SPM-120: the safety review. Only organisers and staff mount this, and the
       server refuses everyone else. -->
  <section v-if="showPanel" class="panel safety" data-testid="safety-review">
    <div class="panel-head">
      <h2>Safety review</h2>
      <span v-if="latest" class="state" :class="latest.status">{{ STATE_LABELS[latest.status] }}</span>
      <button
        v-if="canSubmit && !submitting"
        type="button"
        class="btn btn-outline small"
        data-testid="safety-submit-open"
        @click="openSubmit"
      >
        {{ latest ? 'Submit again' : 'Submit for safety review' }}
      </button>
    </div>
    <p v-if="loadError" class="form-error">{{ loadError }}</p>

    <!-- AC1: offered in planning; the server refuses until venue and equipment are confirmed. -->
    <form v-if="submitting" class="submit-form" data-testid="safety-submit-form" @submit.prevent="submit">
      <p class="hint">
        The Safety Officer sees the confirmed venue and equipment with these notes. The event waits in Safety
        review until they decide.
      </p>
      <label for="safety-crowd">Crowd movement</label>
      <textarea
        id="safety-crowd"
        v-model="crowdMovement"
        rows="3"
        maxlength="4000"
        placeholder="How people arrive, move through, and leave the venue"
        data-testid="safety-crowd-movement"
      ></textarea>
      <label for="safety-placement">Equipment placement</label>
      <textarea
        id="safety-placement"
        v-model="equipmentPlacement"
        rows="2"
        maxlength="4000"
        placeholder="Where each piece of equipment goes (needed when equipment is reserved)"
        data-testid="safety-equipment-placement"
      ></textarea>
      <div v-if="missing.length" class="warning" data-testid="safety-missing">
        <p>Not ready for a safety review yet:</p>
        <ul>
          <li v-for="reason in missing" :key="reason">{{ reason }}</li>
        </ul>
      </div>
      <p v-if="submitError" class="form-error">{{ submitError }}</p>
      <div class="form-actions">
        <button type="button" class="btn btn-ghost small" @click="submitting = false">Cancel</button>
        <button type="submit" class="btn btn-solid small" :disabled="saving || !crowdMovement.trim()" data-testid="safety-submit">
          {{ saving ? 'Submitting…' : 'Submit for safety review' }}
        </button>
      </div>
    </form>

    <p v-if="latest?.status === 'pending' && !isOfficer" class="notice" data-testid="safety-pending">
      Submitted {{ formatUtc(latest.submittedAt) }}. Waiting for a Safety Officer.
    </p>

    <!-- AC3–AC6, AC9: the latest decision, for everyone who can see the panel. -->
    <div v-if="latest && latest.status !== 'pending'" class="outcome" :class="latest.status" data-testid="safety-outcome">
      <p>
        <strong>{{ OUTCOME_TITLES[latest.status] }}</strong>
        by {{ nameOf(latest.decidedBy) }} on {{ formatUtc(latest.decidedAt) }}.
      </p>
      <p v-if="latest.decisionNote">
        {{ NOTE_LABELS[latest.status] }}: {{ latest.decisionNote }}
      </p>
      <p v-if="latest.affected.length">
        Marked for re-checking: {{ latest.affected.map((kind) => AFFECTED_LABELS[kind]).join(' and ') }}.
      </p>
      <p v-if="latest.status === 'rejected'">
        The event is not cancelled. The coordinator can revise the arrangements and submit it again.
      </p>
    </div>

    <!-- AC2: what the officer judges, as it stood when submitted. -->
    <details v-if="latest" class="package" :open="isOfficer && latest.status === 'pending'" data-testid="safety-package">
      <summary>What was submitted</summary>
      <dl class="facts">
        <div>
          <dt>Expected attendance</dt>
          <dd>{{ latest.package.expectedAttendance }}</dd>
        </div>
        <div>
          <dt>When</dt>
          <dd>{{ formatRange(latest.package.proposedStartAt, latest.package.proposedEndAt) }}</dd>
        </div>
      </dl>
      <div v-for="venue in latest.package.venues" :key="venue.venueId" class="venue" data-testid="safety-venue">
        <h3>{{ venue.venueName }}<span v-if="venue.location" class="muted"> · {{ venue.location }}</span></h3>
        <p v-if="venue.needsReverification" class="flag">Marked for re-checking: {{ venue.reverificationNote }}</p>
        <dl class="facts">
          <div>
            <dt>Capacity in layout</dt>
            <dd data-testid="safety-venue-capacity">
              {{ venue.capacityInLayout }}
              <template v-if="venue.layout">({{ venue.layout }})</template>
              <template v-else>(largest layout; {{ latest.package.layout || 'no layout' }} not offered)</template>
            </dd>
          </div>
          <div>
            <dt>Layouts</dt>
            <dd>{{ venue.layouts.map((layout) => `${layout.name} ${layout.capacity}`).join(', ') || 'Not listed' }}</dd>
          </div>
          <div class="wide">
            <dt>Emergency access</dt>
            <dd data-testid="safety-emergency-access">{{ venue.emergencyAccess || 'Not recorded for this venue' }}</dd>
          </div>
          <div class="wide">
            <dt>Known venue restrictions</dt>
            <dd data-testid="safety-restrictions">{{ venue.restrictions || 'None recorded' }}</dd>
          </div>
          <div class="wide">
            <dt>Venue accessibility</dt>
            <dd>{{ venue.accessibilityFeatures.join(', ') || 'None listed' }}</dd>
          </div>
        </dl>
      </div>
      <dl class="facts">
        <div class="wide">
          <dt>Accessibility requirements</dt>
          <dd data-testid="safety-accessibility">
            {{ latest.package.accessibilityRequirements.join(', ') || 'None' }}
            <template v-if="latest.package.accessibilityNote"> · {{ latest.package.accessibilityNote }}</template>
          </dd>
        </div>
        <div class="wide">
          <dt>Equipment</dt>
          <dd>
            <ul v-if="latest.package.equipment.length" class="lines">
              <li v-for="line in latest.package.equipment" :key="line.equipmentId">
                {{ line.quantity }} × {{ line.name }} ({{ line.status }})
                <template v-if="line.technicalRequirements"> · {{ line.technicalRequirements }}</template>
                <span v-if="line.needsReverification" class="flag inline">Marked for re-checking</span>
              </li>
            </ul>
            <template v-else>No equipment requested</template>
          </dd>
        </div>
        <div class="wide">
          <dt>Equipment placement</dt>
          <dd data-testid="safety-placement">{{ latest.package.equipmentPlacement || 'No equipment to place' }}</dd>
        </div>
        <div class="wide">
          <dt>Crowd movement</dt>
          <dd data-testid="safety-crowd">{{ latest.package.crowdMovement }}</dd>
        </div>
      </dl>
    </details>

    <!-- AC3: Safety Officers decide; the server refuses everyone else with 403 (AC8). -->
    <div v-if="isOfficer && latest?.status === 'pending'" class="decision" data-testid="safety-decision">
      <label for="safety-decision-text">Notes for the coordinator</label>
      <textarea
        id="safety-decision-text"
        v-model="decisionText"
        rows="3"
        maxlength="4000"
        placeholder="Optional to approve; required to reject or request changes"
        data-testid="safety-decision-text"
      ></textarea>
      <fieldset class="affected">
        <legend>If requesting changes, which arrangements should be reviewed again?</legend>
        <label><input v-model="affected" type="checkbox" value="venue" data-testid="safety-affected-venue" /> Venue</label>
        <label><input v-model="affected" type="checkbox" value="technical" data-testid="safety-affected-technical" /> Equipment</label>
      </fieldset>
      <p v-if="decisionError" class="form-error">{{ decisionError }}</p>
      <div class="form-actions">
        <button type="button" class="btn btn-outline small" :disabled="busy || !decisionText.trim()" data-testid="safety-reject" @click="decide('reject')">
          Reject
        </button>
        <button type="button" class="btn btn-outline small" :disabled="busy || !decisionText.trim()" data-testid="safety-request-changes" @click="decide('changes')">
          Request changes
        </button>
        <button type="button" class="btn btn-solid small" :disabled="busy" data-testid="safety-approve" @click="decide('approve')">
          Approve
        </button>
      </div>
    </div>

    <details v-if="reviews.length > 1" class="history" data-testid="safety-history">
      <summary>Earlier reviews ({{ reviews.length - 1 }})</summary>
      <ul>
        <li v-for="review in reviews.slice(1)" :key="review.reviewId">
          {{ STATE_LABELS[review.status] }} · submitted {{ formatUtc(review.submittedAt) }}
          <template v-if="review.decisionNote"> · {{ review.decisionNote }}</template>
        </li>
      </ul>
    </details>

    <p v-if="!reviews.length && !submitting && !loadError" class="empty-note">
      Not submitted yet. It can be submitted once the venue booking and the equipment are confirmed.
    </p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  approveSafetyReview,
  getSafetyReviews,
  rejectSafetyReview,
  requestSafetyChanges,
  submitSafetyReview,
} from '../../api/eventService.js'
import { getUsers } from '../../api/userService.js'
import { SAFETY_SUBMITTABLE_STATUSES } from '../../config/eventStatus.js'
import { session } from '../../store/session.js'
import { formatUtc } from '../../utils/datetime.js'

const props = defineProps({ event: { type: Object, required: true } })
// Submitting or deciding changes the event's status, so the page re-reads it.
const emit = defineEmits(['changed'])

const STATE_LABELS = {
  pending: 'Waiting for review',
  approved: 'Approved',
  rejected: 'Rejected',
  changes_requested: 'Changes requested',
  superseded: 'Withdrawn',
}
const OUTCOME_TITLES = {
  approved: 'Approved for preparation',
  rejected: 'Rejected',
  changes_requested: 'Changes requested',
  superseded: 'Withdrawn because the event changed',
}
const NOTE_LABELS = {
  approved: 'Note',
  rejected: 'Reason',
  changes_requested: 'What must change',
  superseded: 'What changed',
}
const AFFECTED_LABELS = { venue: 'the venue booking', technical: 'the equipment' }

const reviews = ref([])
const names = ref({})
const loaded = ref(false)
const hidden = ref(false)
const loadError = ref('')
const submitting = ref(false)
const crowdMovement = ref('')
const equipmentPlacement = ref('')
const missing = ref([])
const submitError = ref('')
const saving = ref(false)
const decisionText = ref('')
const affected = ref([])
const decisionError = ref('')
const busy = ref(false)

const latest = computed(() => reviews.value[0] || null)
const isOfficer = computed(() => session.role === 'safety')
const canSubmit = computed(
  () =>
    session.role === 'coordinator' &&
    !!props.event.coordinatorId &&
    props.event.coordinatorId === session.userId &&
    SAFETY_SUBMITTABLE_STATUSES.includes(props.event.status),
)
const showPanel = computed(
  () => loaded.value && !hidden.value && (reviews.value.length > 0 || canSubmit.value || !!loadError.value),
)

function nameOf(userId) {
  return names.value[userId] || 'a Safety Officer'
}

function formatRange(start, end) {
  if (!start || !end) return 'Date not set'
  return `${new Date(start).toLocaleString()} – ${new Date(end).toLocaleString()}`
}

function errorText(err, fallback) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(' ')
  return detail?.message || fallback
}

async function load() {
  try {
    const { data } = await getSafetyReviews(props.event.eventId)
    reviews.value = data
  } catch (err) {
    // A 403 means this viewer may not see safety reviews at all, so show nothing.
    if (err.response?.status === 403) hidden.value = true
    else loadError.value = errorText(err, 'Could not load the safety review.')
  } finally {
    loaded.value = true
  }
}

// Names are for display only; without them the panel still works.
async function loadNames() {
  try {
    const { data } = await getUsers()
    names.value = Object.fromEntries(data.map((user) => [user.userId, user.userName]))
  } catch {
    names.value = {}
  }
}

function openSubmit() {
  missing.value = []
  submitError.value = ''
  submitting.value = true
}

async function submit() {
  saving.value = true
  missing.value = []
  submitError.value = ''
  try {
    await submitSafetyReview(props.event.eventId, crowdMovement.value, equipmentPlacement.value)
    submitting.value = false
    await load()
    emit('changed')
  } catch (err) {
    const detail = err.response?.data?.detail
    if (err.response?.status === 409 && Array.isArray(detail?.missing)) {
      missing.value = detail.message.split(/(?<=\.)\s+/)
    } else {
      submitError.value = errorText(err, 'Could not submit for a safety review. Please try again.')
    }
  } finally {
    saving.value = false
  }
}

async function decide(kind) {
  busy.value = true
  decisionError.value = ''
  const { eventId } = props.event
  const reviewId = latest.value.reviewId
  try {
    if (kind === 'approve') await approveSafetyReview(eventId, reviewId, decisionText.value)
    else if (kind === 'reject') await rejectSafetyReview(eventId, reviewId, decisionText.value)
    else await requestSafetyChanges(eventId, reviewId, decisionText.value, affected.value)
    decisionText.value = ''
    affected.value = []
    await load()
    emit('changed')
  } catch (err) {
    decisionError.value = errorText(err, 'Could not record the decision. Please try again.')
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  load()
  loadNames()
})
</script>

<style scoped>
.panel {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 22px 24px;
  margin-top: 18px;
}
.panel-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.panel-head h2 { margin: 0; font-size: 16px; font-weight: 500; }
.panel-head .btn { margin-left: auto; }
.empty-note, .hint { font-size: 13px; color: var(--muted); line-height: 1.55; margin: 0 0 12px; }
.btn.small { padding: 7px 14px; font-size: 13px; }
.btn:disabled { opacity: .55; cursor: not-allowed; }

.state { font-size: 10px; letter-spacing: .06em; text-transform: uppercase; border-radius: 999px; padding: 2px 9px; border: 1px solid var(--hairline); color: var(--muted); }
.state.pending, .state.changes_requested { color: #FFD9A8; background: rgba(255, 170, 80, .1); border-color: rgba(255, 196, 120, .35); }
.state.approved { color: var(--halo); background: rgba(124, 77, 255, .18); border-color: rgba(167, 139, 250, .3); }
.state.rejected { color: #FF8A76; background: rgba(255, 138, 118, .08); border-color: rgba(255, 138, 118, .3); }

label, .facts dt, legend {
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
}
label { display: block; margin-bottom: 6px; }
textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  padding: 10px 12px;
  margin-bottom: 12px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--text);
  font-family: 'Inter', sans-serif;
  resize: vertical;
}
textarea:focus { outline: none; border-color: rgba(167, 139, 250, .6); box-shadow: 0 0 0 3px rgba(124, 77, 255, .16); }

.submit-form, .decision { border: 1px solid var(--hairline); border-radius: 12px; padding: 16px; margin: 0 0 14px; }
.form-actions { display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.affected { border: none; padding: 0; margin: 0 0 12px; display: flex; flex-wrap: wrap; gap: 6px 18px; }
.affected legend { margin-bottom: 8px; padding: 0; }
.affected label { display: flex; align-items: center; gap: 8px; margin: 0; font-size: 13px; letter-spacing: 0; text-transform: none; color: var(--body); }

.notice, .outcome, .warning {
  font-size: 13px;
  line-height: 1.6;
  border-radius: 9px;
  padding: 11px 14px;
  margin: 0 0 14px;
}
.notice { color: var(--halo); background: rgba(124, 77, 255, .1); border: 1px solid rgba(167, 139, 250, .25); }
.outcome { color: var(--body); border: 1px solid var(--hairline); }
.outcome p, .warning p, .warning ul { margin: 0; }
.outcome p + p { margin-top: 6px; }
.outcome.approved strong { color: var(--halo); }
.outcome.rejected strong { color: #FF8A76; }
.outcome.changes_requested strong { color: #FFD9A8; }
.warning { color: #FFD9A8; background: rgba(255, 170, 80, .08); border: 1px solid rgba(255, 196, 120, .3); }

.package, .history { border-top: 1px solid var(--hairline); padding-top: 12px; margin-bottom: 12px; }
.package summary, .history summary { cursor: pointer; font-size: 13px; color: var(--body); margin-bottom: 10px; }
.venue h3 { font-size: 14px; font-weight: 500; margin: 12px 0 8px; }
.muted { color: var(--muted); font-weight: 400; }
.facts { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 20px; margin: 0 0 8px; }
.facts .wide { grid-column: 1 / -1; }
.facts dd { margin: 4px 0 0; font-size: 14px; color: var(--body); line-height: 1.55; white-space: pre-wrap; }
.lines { margin: 0; padding-left: 18px; }
.flag { font-size: 12px; color: #FFD9A8; margin: 0 0 8px; }
.flag.inline { margin-left: 8px; font-size: 11px; }
.history ul { margin: 0; padding-left: 18px; font-size: 13px; color: var(--body); line-height: 1.6; }

.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 0 0 12px;
}

@media (max-width: 560px) {
  .panel { padding: 18px 16px; }
  .facts { grid-template-columns: 1fr; }
}
</style>
