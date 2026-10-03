<template>
  <div class="event-page">
    <button type="button" class="btn btn-ghost back" @click="goBack">← Event details</button>

    <p v-if="loading" class="empty-note">Loading registration settings…</p>
    <p v-else-if="loadError" class="form-error">{{ loadError }}</p>

    <template v-else>
      <header class="page-head">
        <div>
          <p class="eyebrow">Registration settings</p>
          <h1>{{ event.eventName }}</h1>
        </div>
      </header>

      <p v-if="!canEdit" class="notice" data-testid="registration-settings-readonly">
        {{ readOnlyReason }}
      </p>

      <form class="panel" @submit.prevent="save()">
        <label class="toggle">
          <input v-model="form.registrationEnabled" type="checkbox" :disabled="!canEdit" data-testid="registration-enabled" />
          This event needs attendees to register
        </label>

        <div class="grid">
          <div>
            <label for="registration-opens">Registration opens</label>
            <input
              id="registration-opens"
              v-model="form.registrationOpensAt"
              type="datetime-local"
              :disabled="!canEdit"
              data-testid="registration-opens"
            />
          </div>
          <div>
            <label for="registration-closes">Registration closes</label>
            <input
              id="registration-closes"
              v-model="form.registrationClosesAt"
              type="datetime-local"
              :max="eventStartInput"
              :disabled="!canEdit"
              data-testid="registration-closes"
            />
          </div>
          <div>
            <label for="registration-capacity">Capacity</label>
            <input
              id="registration-capacity"
              v-model.number="form.capacity"
              type="number"
              min="0"
              :disabled="!canEdit"
              data-testid="registration-capacity"
            />
          </div>
        </div>
        <p class="hint">
          Registration must close by the event start ({{ formatWhen(event.proposedStartAt) }}).
          {{ event.registeredCount }} {{ event.registeredCount === 1 ? 'person is' : 'people are' }} registered now,
          so the capacity cannot go below that.
        </p>

        <!-- SPM-90 AC3/AC5: nothing is saved until the coordinator confirms. -->
        <div v-if="warnings.length" class="warning-box">
          <p
            v-for="warning in warnings"
            :key="warning.kind"
            :data-testid="warning.kind === 'venueCapacity' ? 'capacity-venue-warning' : 'registration-off-warning'"
          >
            {{ warning.message }}
          </p>
          <div class="form-actions">
            <button type="button" class="btn btn-ghost" @click="warnings = []">Go back</button>
            <button
              type="button"
              class="btn btn-solid"
              :disabled="saving"
              :data-testid="hasVenueWarning ? 'capacity-confirm' : 'registration-off-confirm'"
              @click="save(confirmations)"
            >
              {{ saving ? 'Saving…' : 'Save anyway' }}
            </button>
          </div>
        </div>

        <p v-if="error" class="form-error" data-testid="registration-settings-error">{{ error }}</p>
        <p v-if="savedNote" class="notice" data-testid="registration-settings-saved">{{ savedNote }}</p>

        <div v-if="canEdit && !warnings.length" class="form-actions">
          <button type="submit" class="btn btn-solid" :disabled="saving" data-testid="registration-save">
            {{ saving ? 'Saving…' : 'Save settings' }}
          </button>
        </div>
      </form>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getEvent, updateRegistrationSettings } from '../../api/eventService.js'
import { REGISTRATION_SETUP_STATUSES } from '../../config/eventStatus.js'
import { session } from '../../store/session.js'

const route = useRoute()
const router = useRouter()

const event = ref(null)
const loading = ref(true)
const loadError = ref('')
const form = reactive({ registrationEnabled: false, registrationOpensAt: '', registrationClosesAt: '', capacity: 0 })
let original = {}
const warnings = ref([])
const saving = ref(false)
const error = ref('')
const savedNote = ref('')

// datetime-local inputs need "YYYY-MM-DDTHH:mm"; the API returns full ISO strings.
const toInputDatetime = (iso) => (iso ? iso.slice(0, 16) : '')
const eventStartInput = computed(() => toInputDatetime(event.value?.proposedStartAt))

// SPM-90 AC1: the assigned coordinator, from planning until confirmed. The server checks the same.
const canEdit = computed(
  () =>
    session.role === 'coordinator' &&
    !!event.value?.coordinatorId &&
    event.value.coordinatorId === session.userId &&
    REGISTRATION_SETUP_STATUSES.includes(event.value.status),
)
const readOnlyReason = computed(() => {
  if (session.role !== 'coordinator' || event.value?.coordinatorId !== session.userId) {
    return 'Only the event’s assigned coordinator can change these settings.'
  }
  return `Registration is set up from planning until the event is confirmed. This event is ${event.value.status}.`
})
const hasVenueWarning = computed(() => warnings.value.some((warning) => warning.kind === 'venueCapacity'))
const confirmations = computed(() => ({
  confirmOverVenueCapacity: hasVenueWarning.value,
  confirmRegistrationOff: warnings.value.some((warning) => warning.kind === 'registrationOff'),
}))

function formatWhen(value) {
  return value ? new Date(value).toLocaleString() : 'not set'
}

function fill(data) {
  event.value = data
  Object.assign(form, {
    registrationEnabled: !!data.registrationEnabled,
    registrationOpensAt: toInputDatetime(data.registrationOpensAt),
    registrationClosesAt: toInputDatetime(data.registrationClosesAt),
    capacity: data.capacity ?? 0,
  })
  original = { ...form }
}

// Changed fields only, so an untouched date is never logged as edited. The
// capacity always goes: the venue booking and the registrations it must fit
// can change without anyone touching this form.
function payload() {
  const body = { capacity: form.capacity }
  for (const field of ['registrationEnabled', 'registrationOpensAt', 'registrationClosesAt']) {
    if (form[field] !== original[field]) body[field] = form[field] === '' ? null : form[field]
  }
  return body
}

function validate() {
  if (!Number.isInteger(form.capacity) || form.capacity < 0) return 'Enter a capacity of 0 or more.'
  const { registrationOpensAt: opens, registrationClosesAt: closes } = form
  // Like the server, only a period being changed is checked.
  if (opens === original.registrationOpensAt && closes === original.registrationClosesAt) return ''
  if (opens && closes && closes <= opens) return 'Registration must close after it opens.'
  if (closes && eventStartInput.value && closes > eventStartInput.value) {
    return 'Registration must close no later than the event starts.'
  }
  return ''
}

function describe(detail) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(' ')
  return detail?.message || ''
}

async function save(confirm = {}) {
  error.value = validate()
  savedNote.value = ''
  if (error.value) return
  saving.value = true
  try {
    const { data } = await updateRegistrationSettings(event.value.eventId, payload(), confirm)
    warnings.value = []
    fill(data)
    savedNote.value = data.notifiedAttendees
      ? `Saved. The organiser and ${data.notifiedAttendees} registered ${data.notifiedAttendees === 1 ? 'attendee were' : 'attendees were'} notified.`
      : 'Saved. The organiser has been notified of any change.'
  } catch (err) {
    const detail = err.response?.data?.detail
    if (err.response?.status === 409 && detail?.requiresConfirmation) {
      warnings.value = detail.warnings
    } else {
      warnings.value = []
      error.value = describe(detail) || 'Could not save the registration settings. Please try again.'
    }
  } finally {
    saving.value = false
  }
}

function goBack() {
  router.push(`/app/events/${route.params.id}`)
}

async function load() {
  try {
    const { data } = await getEvent(route.params.id)
    fill(data)
  } catch (err) {
    loadError.value = describe(err.response?.data?.detail) || 'Could not load this event. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.event-page { max-width: 760px; margin: 0 auto; padding: 28px 32px 48px; }
.back { margin: 0 0 18px -18px; padding-left: 18px; }
.empty-note { font-size: 14px; color: var(--muted); }

.page-head { margin-bottom: 22px; }
.page-head h1 { margin: 6px 0 0; font-size: 28px; font-weight: 500; letter-spacing: -.02em; }

.panel {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 22px 24px;
}

label {
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
  display: block;
  margin-bottom: 6px;
}
.toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  letter-spacing: 0;
  text-transform: none;
  color: var(--text);
  margin-bottom: 18px;
}
.toggle input { width: 16px; height: 16px; }

.grid { display: grid; grid-template-columns: 1fr 1fr 140px; gap: 16px; }
input[type='datetime-local'],
input[type='number'] {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  padding: 0 12px;
  height: 42px;
  font-size: 14px;
  color: var(--text);
  font-family: 'Inter', sans-serif;
}
input:focus { outline: none; border-color: rgba(167, 139, 250, .6); box-shadow: 0 0 0 3px rgba(124, 77, 255, .16); }
input:disabled { opacity: .6; }
.hint { font-size: 12px; color: var(--muted); line-height: 1.6; margin: 12px 0 0; }

.warning-box {
  margin-top: 18px;
  font-size: 13px;
  line-height: 1.6;
  color: #FFD9A8;
  background: rgba(255, 170, 80, .08);
  border: 1px solid rgba(255, 196, 120, .3);
  border-radius: 9px;
  padding: 12px 14px;
}
.warning-box p { margin: 0 0 6px; }

.notice {
  font-size: 13px;
  line-height: 1.6;
  color: var(--halo);
  background: rgba(124, 77, 255, .1);
  border: 1px solid rgba(167, 139, 250, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 16px 0 0;
}
.page-head + .notice { margin: 0 0 16px; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 16px 0 0;
}
.form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.btn:disabled { opacity: .55; cursor: not-allowed; }

@media (max-width: 720px) {
  .event-page { padding: 22px 16px 36px; }
  .grid { grid-template-columns: 1fr; }
  .back { margin-left: 0; }
}
</style>
