<template>
  <!-- SPM-106: change requests. Only organisers and staff mount this, and the
       server refuses everyone else. -->
  <section v-if="showPanel" class="panel change-requests" data-testid="change-requests">
    <div class="panel-head">
      <h2>Change requests</h2>
      <button
        v-if="canRaise && !raising"
        type="button"
        class="btn btn-outline small"
        data-testid="raise-change-request"
        @click="openRaise"
      >
        Request a change
      </button>
    </div>
    <p v-if="loadError" class="form-error">{{ loadError }}</p>

    <form v-if="raising" class="raise-form" data-testid="change-request-form" @submit.prevent="submitRaise">
      <p class="hint">
        Choose what should change and give the new value. Nothing changes on the event until your coordinator
        accepts it.
      </p>
      <fieldset class="fields">
        <legend>What should change?</legend>
        <label v-for="field in CHANGEABLE_FIELDS" :key="field" class="pick">
          <input
            type="checkbox"
            :checked="field in proposed"
            :data-testid="`change-request-field-${field}`"
            @change="toggleField(field)"
          />
          {{ fieldLabel(field) }}
        </label>
      </fieldset>

      <div v-for="(value, field) in proposed" :key="field" class="value">
        <label :for="`change-${field}`">
          New {{ fieldLabel(field).toLowerCase() }}
          <span class="now">now: {{ formatValue(field, event[field]) }}</span>
        </label>
        <textarea
          v-if="LONG_TEXT.includes(field)"
          :id="`change-${field}`"
          v-model="proposed[field]"
          rows="2"
          :data-testid="`change-request-value-${field}`"
        ></textarea>
        <input
          v-else-if="field === 'proposedStartAt' || field === 'proposedEndAt'"
          :id="`change-${field}`"
          v-model="proposed[field]"
          type="datetime-local"
          :data-testid="`change-request-value-${field}`"
        />
        <input
          v-else-if="field === 'expectedAttendance'"
          :id="`change-${field}`"
          v-model.number="proposed[field]"
          type="number"
          min="0"
          :data-testid="`change-request-value-${field}`"
        />
        <input
          v-else
          :id="`change-${field}`"
          v-model="proposed[field]"
          type="text"
          :list="field === 'category' ? 'change-categories' : field === 'layoutPreference' ? 'change-layouts' : undefined"
          :data-testid="`change-request-value-${field}`"
        />
      </div>
      <datalist id="change-categories">
        <option v-for="option in EVENT_CATEGORIES" :key="option" :value="option" />
      </datalist>
      <datalist id="change-layouts">
        <option v-for="option in LAYOUT_TYPES" :key="option" :value="option" />
      </datalist>

      <label for="change-reason">Why is this changing?</label>
      <textarea id="change-reason" v-model="reason" rows="2" maxlength="2000" data-testid="change-request-reason"></textarea>

      <p v-if="formError" class="form-error">{{ formError }}</p>
      <div class="form-actions">
        <button type="button" class="btn btn-ghost small" @click="raising = false">Cancel</button>
        <button type="submit" class="btn btn-solid small" :disabled="saving" data-testid="change-request-submit">
          {{ saving ? 'Sending…' : 'Send request' }}
        </button>
      </div>
    </form>

    <!-- AC4: pending, with the proposed values, for both sides. AC10: the event above still shows its agreed details. -->
    <div v-if="pending" class="request pending" data-testid="pending-change-request">
      <div class="request-head">
        <strong>Change requested</strong>
        <span class="state pending">Pending</span>
        <span class="when">{{ formatUtc(pending.createdAt) }}</span>
      </div>
      <table class="changes">
        <thead>
          <tr><th>Field</th><th>Current</th><th>Proposed</th></tr>
        </thead>
        <tbody>
          <tr v-for="(value, field) in pending.proposedChanges" :key="field">
            <td>{{ fieldLabel(field) }}</td>
            <td>{{ formatValue(field, pending.currentValues?.[field] ?? event[field]) }}</td>
            <td class="proposed">{{ formatValue(field, value) }}</td>
          </tr>
        </tbody>
      </table>
      <p class="reason"><span>Reason</span>{{ pending.reason }}</p>
      <p class="hint">Nothing changes on the event until the coordinator accepts this.</p>

      <div v-if="canWithdraw" class="form-actions">
        <button
          type="button"
          class="btn btn-outline small"
          :disabled="busy"
          data-testid="change-request-withdraw"
          @click="withdraw"
        >
          Withdraw request
        </button>
      </div>

      <div v-if="isAssignedCoordinator" class="decision">
        <label for="change-decision-reason">Reason for the organiser</label>
        <textarea
          id="change-decision-reason"
          v-model="decisionReason"
          rows="2"
          maxlength="2000"
          placeholder="Required to decline; optional to accept"
          data-testid="change-request-decision-reason"
        ></textarea>
        <div v-if="acceptWarning" class="warning" data-testid="change-request-accept-warning">
          <p>{{ acceptWarning.message }}</p>
          <ul v-if="acceptWarning.arrangements?.length">
            <li v-for="arrangement in acceptWarning.arrangements" :key="arrangement.id">{{ arrangement.summary }}</li>
          </ul>
        </div>
        <div class="form-actions">
          <button
            type="button"
            class="btn btn-outline small"
            :disabled="busy || !decisionReason.trim()"
            data-testid="change-request-decline"
            @click="decline"
          >
            Decline
          </button>
          <button
            v-if="!acceptWarning"
            type="button"
            class="btn btn-solid small"
            :disabled="busy"
            data-testid="change-request-accept"
            @click="accept(false)"
          >
            Accept and apply
          </button>
          <button
            v-else
            type="button"
            class="btn btn-solid small"
            :disabled="busy"
            data-testid="change-request-accept-confirm"
            @click="accept(true)"
          >
            Apply anyway
          </button>
        </div>
      </div>
      <p v-if="actionError" class="form-error">{{ actionError }}</p>
    </div>

    <!-- AC7: the coordinator's decision and reason. -->
    <p v-if="outcome" class="outcome" :class="outcome.status" data-testid="change-request-outcome">
      <strong>Change request {{ outcome.status }}</strong> {{ formatUtc(outcome.reviewedAt) }}
      ({{ Object.keys(outcome.proposedChanges).map(fieldLabel).join(', ').toLowerCase() }})<template
        v-if="outcome.decisionReason"
      >. Reason: {{ outcome.decisionReason }}</template>
    </p>

    <p v-if="!requests.length && !raising && !loadError" class="empty-note">No changes have been requested.</p>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  acceptChangeRequest,
  declineChangeRequest,
  getChangeRequests,
  raiseChangeRequest,
  withdrawChangeRequest,
} from '../../api/eventService.js'
import { CHANGEABLE_FIELDS, EVENT_CATEGORIES, LAYOUT_TYPES, fieldLabel } from '../../config/eventFields.js'
import { CHANGE_REQUEST_STATUSES } from '../../config/eventStatus.js'
import { session } from '../../store/session.js'
import { formatUtc } from '../../utils/datetime.js'

const props = defineProps({ event: { type: Object, required: true } })
// Accepting changes the event, so the page re-reads it.
const emit = defineEmits(['changed'])

const LONG_TEXT = ['description', 'purpose', 'accessibilityNeeds', 'equipmentRequirements']
const DATETIMES = ['proposedStartAt', 'proposedEndAt']
// Cleared, these go to the API as null rather than "".
const CLEARABLE = ['category', 'layoutPreference']

const requests = ref([])
const loaded = ref(false)
const loadError = ref('')
const hidden = ref(false)
const raising = ref(false)
const proposed = reactive({})
const reason = ref('')
const saving = ref(false)
const formError = ref('')
const decisionReason = ref('')
const acceptWarning = ref(null)
const busy = ref(false)
const actionError = ref('')

// Newest first, so these are the latest of each.
const pending = computed(() => requests.value.find((row) => row.status === 'pending'))
const outcome = computed(() => requests.value.find((row) => row.status === 'accepted' || row.status === 'declined'))
const isAssignedCoordinator = computed(
  () => session.role === 'coordinator' && !!props.event.coordinatorId && props.event.coordinatorId === session.userId,
)
// AC1/AC8/AC9: organisers only, at the right stage (never a draft), one pending at a time (AC5).
const canRaise = computed(
  () => session.role === 'organiser' && CHANGE_REQUEST_STATUSES.includes(props.event.status) && !pending.value,
)
const canWithdraw = computed(() => !!pending.value && pending.value.requestedBy === session.userId)
const showPanel = computed(
  () => loaded.value && !hidden.value && (requests.value.length > 0 || canRaise.value || !!loadError.value),
)

// datetime-local inputs need "YYYY-MM-DDTHH:mm"; the API returns full ISO strings.
const toInputDatetime = (iso) => (iso ? iso.slice(0, 16) : '')

function formatValue(field, value) {
  if (value === null || value === undefined || value === '') return 'Not set'
  if (DATETIMES.includes(field)) {
    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString()
  }
  return String(value)
}

function errorText(err, fallback) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(' ')
  return detail?.message || fallback
}

async function load() {
  try {
    const { data } = await getChangeRequests(props.event.eventId)
    requests.value = data
  } catch (err) {
    // A 403 means this viewer may not see change requests at all, so show nothing.
    if (err.response?.status === 403) hidden.value = true
    else loadError.value = errorText(err, 'Could not load change requests.')
  } finally {
    loaded.value = true
  }
}

function openRaise() {
  for (const field of Object.keys(proposed)) delete proposed[field]
  reason.value = ''
  formError.value = ''
  raising.value = true
}

function toggleField(field) {
  if (field in proposed) {
    delete proposed[field]
  } else {
    const current = props.event[field]
    proposed[field] = DATETIMES.includes(field) ? toInputDatetime(current) : current ?? ''
  }
}

function payload() {
  const changes = {}
  for (const [field, value] of Object.entries(proposed)) {
    changes[field] = CLEARABLE.includes(field) && value === '' ? null : value
  }
  return changes
}

function validate() {
  if (!Object.keys(proposed).length) return 'Choose at least one thing to change.'
  if (!reason.value.trim()) return 'Say why the change is needed.'
  if ('eventName' in proposed && !String(proposed.eventName).trim()) return 'The event needs a name.'
  if ('expectedAttendance' in proposed && (!Number.isInteger(proposed.expectedAttendance) || proposed.expectedAttendance < 0)) {
    return 'Enter an attendance of 0 or more.'
  }
  return ''
}

async function submitRaise() {
  formError.value = validate()
  if (formError.value) return
  saving.value = true
  try {
    await raiseChangeRequest(props.event.eventId, payload(), reason.value)
    raising.value = false
    await load()
  } catch (err) {
    formError.value = errorText(err, 'Could not send the request. Please try again.')
  } finally {
    saving.value = false
  }
}

async function act(action, fallback) {
  busy.value = true
  actionError.value = ''
  try {
    await action()
    acceptWarning.value = null
    decisionReason.value = ''
    await load()
  } catch (err) {
    const detail = err.response?.data?.detail
    if (err.response?.status === 409 && detail?.requiresConfirmation) {
      acceptWarning.value = detail
    } else {
      actionError.value = errorText(err, fallback)
    }
  } finally {
    busy.value = false
  }
}

function withdraw() {
  return act(() => withdrawChangeRequest(props.event.eventId, pending.value.changeRequestId), 'Could not withdraw the request.')
}

function decline() {
  return act(
    () => declineChangeRequest(props.event.eventId, pending.value.changeRequestId, decisionReason.value),
    'Could not decline the request.',
  )
}

function accept(confirm) {
  return act(async () => {
    await acceptChangeRequest(props.event.eventId, pending.value.changeRequestId, decisionReason.value, confirm)
    emit('changed')
  }, 'Could not accept the request.')
}

onMounted(load)
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
.panel-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 14px; }
.panel h2 { margin: 0; font-size: 16px; font-weight: 500; }
.empty-note { font-size: 14px; color: var(--muted); margin: 0; }
.hint { font-size: 12px; color: var(--muted); line-height: 1.5; margin: 0 0 12px; }

.btn.small { padding: 7px 14px; font-size: 13px; }
.btn:disabled { opacity: .55; cursor: not-allowed; }

label {
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
  display: block;
  margin-bottom: 6px;
}
.now { text-transform: none; letter-spacing: 0; margin-left: 6px; }
input[type='text'],
input[type='number'],
input[type='datetime-local'],
textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  padding: 0 12px;
  height: 42px;
  margin-bottom: 12px;
  font-size: 14px;
  color: var(--text);
  font-family: 'Inter', sans-serif;
}
textarea { height: auto; padding: 10px 12px; resize: vertical; line-height: 1.5; }
input:focus, textarea:focus { outline: none; border-color: rgba(167, 139, 250, .6); box-shadow: 0 0 0 3px rgba(124, 77, 255, .16); }

.raise-form { border: 1px solid var(--hairline); border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.fields { border: none; margin: 0 0 12px; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 6px 12px; }
.fields legend { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; padding: 0; }
.pick { display: flex; align-items: center; gap: 8px; font-size: 13px; text-transform: none; letter-spacing: 0; color: var(--body); margin: 0; }
.form-actions { display: flex; justify-content: flex-end; gap: 8px; }

.request { border: 1px solid var(--hairline); border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; }
.request-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.when { font-size: 12px; color: var(--muted); margin-left: auto; }
.state { font-size: 10px; letter-spacing: .06em; text-transform: uppercase; border-radius: 999px; padding: 2px 9px; }
.state.pending { color: #FFD9A8; background: rgba(255, 170, 80, .1); border: 1px solid rgba(255, 196, 120, .35); }

.changes { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 10px; }
.changes th { text-align: left; font-size: 10px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); font-weight: 400; padding: 4px 8px 6px 0; }
.changes td { padding: 6px 8px 6px 0; border-top: 1px solid var(--hairline); color: var(--body); vertical-align: top; word-break: break-word; }
.changes td.proposed { color: var(--text); }
.reason { font-size: 13px; color: var(--body); margin: 0 0 8px; line-height: 1.5; }
.reason span { font-size: 10px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); margin-right: 8px; }

.decision { border-top: 1px solid var(--hairline); padding-top: 12px; margin-top: 4px; }
.warning {
  font-size: 13px;
  line-height: 1.6;
  color: #FFD9A8;
  background: rgba(255, 170, 80, .08);
  border: 1px solid rgba(255, 196, 120, .3);
  border-radius: 9px;
  padding: 10px 14px;
  margin-bottom: 12px;
}
.warning p, .warning ul { margin: 0; }

.outcome { font-size: 13px; line-height: 1.6; color: var(--body); margin: 0 0 8px; }
.outcome.declined strong { color: #FF8A76; }
.outcome.accepted strong { color: var(--halo); }

.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 8px 0 0;
}

@media (max-width: 560px) {
  .panel { padding: 18px 16px; }
  .when { margin-left: 0; }
}
</style>
