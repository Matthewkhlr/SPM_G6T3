<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <!-- Step 2 (SPM-71 AC3): the server named the arrangements this change affects. -->
    <div v-if="pending" class="modal" data-testid="edit-confirm-dialog">
      <h3>Confirm this change</h3>
      <p>{{ pending.message }}</p>
      <ul class="affected" data-testid="edit-affected">
        <li v-for="item in pending.arrangements" :key="item.id" :data-testid="`edit-affected-${item.id}`">
          {{ item.summary }}
        </li>
        <li v-if="pending.statusChange">
          Event status: {{ eventStatusLabel(pending.statusChange.from) }} →
          {{ eventStatusLabel(pending.statusChange.to) }}
        </li>
      </ul>
      <p v-if="error" class="form-error">{{ error }}</p>
      <div class="modal-actions">
        <button type="button" class="btn btn-outline" :disabled="saving" @click="pending = null">Go back</button>
        <button type="button" class="btn btn-solid" :disabled="saving" data-testid="edit-confirm" @click="save(true)">
          {{ saving ? 'Saving…' : 'Confirm and save' }}
        </button>
      </div>
    </div>

    <!-- Step 1: the form. -->
    <form v-else class="modal edit-modal" data-testid="event-edit-form" novalidate @submit.prevent="save(false)">
      <h3>Edit event</h3>

      <label for="edit-eventName">Event name</label>
      <input id="edit-eventName" v-model.trim="form.eventName" type="text" maxlength="255" />

      <div class="row">
        <div class="col">
          <label for="edit-category">Category</label>
          <select id="edit-category" v-model="form.category">
            <option value="">Not specified</option>
            <option v-for="option in categoryOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </div>
        <div class="col">
          <label for="edit-organiserContact">Organiser contact</label>
          <input id="edit-organiserContact" v-model.trim="form.organiserContact" type="text" maxlength="255" />
        </div>
      </div>

      <label for="edit-purpose">Purpose</label>
      <textarea id="edit-purpose" v-model="form.purpose" rows="2" />

      <label for="edit-description">Description</label>
      <textarea id="edit-description" v-model="form.description" rows="3" />

      <label for="edit-internalNotes">Internal notes <span class="note">Staff only</span></label>
      <textarea id="edit-internalNotes" v-model="form.internalNotes" rows="2" />

      <div class="significant">
        <p class="significant-head">
          Planning details
          <span class="note">Changing these may affect a confirmed venue booking or equipment reservation.</span>
        </p>

        <div class="row">
          <div class="col">
            <label for="edit-start">Starts</label>
            <input id="edit-start" v-model="form.proposedStartAt" type="datetime-local" />
          </div>
          <div class="col">
            <label for="edit-end">Ends</label>
            <input id="edit-end" v-model="form.proposedEndAt" type="datetime-local" />
          </div>
        </div>

        <div class="row">
          <div class="col">
            <label for="edit-attendance">Expected attendance</label>
            <input id="edit-attendance" v-model.number="form.expectedAttendance" type="number" min="0" step="1" />
          </div>
          <div class="col">
            <label for="edit-layout">Required layout</label>
            <input id="edit-layout" v-model.trim="form.layoutPreference" type="text" list="edit-layout-types" />
            <datalist id="edit-layout-types">
              <option v-for="layout in LAYOUT_TYPES" :key="layout" :value="layout" />
            </datalist>
          </div>
        </div>

        <label for="edit-accessibility">Accessibility needs</label>
        <textarea id="edit-accessibility" v-model="form.accessibilityNeeds" rows="2" />

        <label for="edit-equipment">Equipment requirements</label>
        <textarea id="edit-equipment" v-model="form.equipmentRequirements" rows="2" />
      </div>

      <p v-if="error" class="form-error" data-testid="edit-error">{{ error }}</p>
      <div class="modal-actions">
        <button type="button" class="btn btn-outline" @click="emit('close')">Cancel</button>
        <button type="submit" class="btn btn-solid" :disabled="saving || !hasChanges" data-testid="edit-save">
          {{ saving ? 'Saving…' : 'Save changes' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { updateEvent } from '../../api/eventService.js'
import { EVENT_CATEGORIES, LAYOUT_TYPES } from '../../config/eventFields.js'
import { eventStatusLabel } from '../../config/eventStatus.js'

const props = defineProps({
  event: { type: Object, required: true },
  internalNotes: { type: String, default: '' },
})
const emit = defineEmits(['close', 'saved'])

const CATEGORIES = EVENT_CATEGORIES
// Cleared, these go to the API as null rather than "".
const CLEARABLE = ['category', 'layoutPreference']

// datetime-local inputs need "YYYY-MM-DDTHH:mm"; the API returns full ISO strings.
const toInputDatetime = (iso) => (iso ? iso.slice(0, 16) : '')

const original = {
  eventName: props.event.eventName || '',
  category: props.event.category || '',
  organiserContact: props.event.organiserContact || '',
  purpose: props.event.purpose || '',
  description: props.event.description || '',
  internalNotes: props.internalNotes || '',
  proposedStartAt: toInputDatetime(props.event.proposedStartAt),
  proposedEndAt: toInputDatetime(props.event.proposedEndAt),
  expectedAttendance: props.event.expectedAttendance ?? 0,
  layoutPreference: props.event.layoutPreference || '',
  accessibilityNeeds: props.event.accessibilityNeeds || '',
  equipmentRequirements: props.event.equipmentRequirements || '',
}
const form = reactive({ ...original })
const saving = ref(false)
const error = ref('')
const pending = ref(null)

// An existing category outside the usual four stays selectable.
const categoryOptions = computed(() =>
  original.category && !CATEGORIES.includes(original.category) ? [...CATEGORIES, original.category] : CATEGORIES,
)

// Only the fields that changed are sent, so an untouched field is never logged as edited.
const changes = computed(() => {
  const changed = {}
  for (const [field, before] of Object.entries(original)) {
    const value = form[field]
    if (value === before) continue
    changed[field] = CLEARABLE.includes(field) && value === '' ? null : value
  }
  return changed
})
const hasChanges = computed(() => Object.keys(changes.value).length > 0)

function validate() {
  if (!form.eventName) return 'Event name is required.'
  if (!form.proposedStartAt || !form.proposedEndAt) return 'Start and end are both required.'
  if (new Date(form.proposedEndAt) <= new Date(form.proposedStartAt)) return 'The end must be after the start.'
  if (!Number.isInteger(form.expectedAttendance) || form.expectedAttendance < 0) {
    return 'Enter an attendance of 0 or more.'
  }
  return ''
}

function describe(detail) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(' ')
  return detail?.message || ''
}

async function save(confirmSignificantChange) {
  error.value = validate()
  if (error.value) return
  saving.value = true
  try {
    const { data } = await updateEvent(props.event.eventId, changes.value, confirmSignificantChange)
    emit('saved', data)
  } catch (err) {
    const detail = err.response?.data?.detail
    if (err.response?.status === 409 && detail?.requiresConfirmation) {
      pending.value = detail
    } else {
      error.value = describe(detail) || 'Could not save the changes. Please try again.'
    }
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(5, 2, 14, .7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center; z-index: 10;
  padding: 16px;
}
.modal {
  background: linear-gradient(160deg, #1A0C3B, #0D0524);
  border: 1px solid rgba(167, 139, 250, .28);
  box-shadow: 0 30px 90px rgba(4, 1, 12, .7), 0 0 60px rgba(124, 77, 255, .18);
  border-radius: 18px;
  padding: 30px;
  width: 440px;
  max-width: 100%;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
}
.edit-modal { width: 640px; }
.modal h3 { margin: 0 0 18px; font-size: 18px; font-weight: 500; }
.modal p { font-size: 14px; line-height: 1.7; color: var(--body); margin: 0 0 6px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }

label {
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
  display: block;
  margin-bottom: 6px;
}
.note { text-transform: none; letter-spacing: 0; font-size: 12px; color: var(--muted); font-weight: 400; }

input,
select,
textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  padding: 0 12px;
  height: 42px;
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--text);
  font-family: 'Inter', sans-serif;
}
textarea { height: auto; padding: 10px 12px; resize: vertical; line-height: 1.5; }
input:focus, select:focus, textarea:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .6);
  box-shadow: 0 0 0 3px rgba(124, 77, 255, .16);
}
select option { background: #150A30; color: var(--text); }

.row { display: flex; gap: 16px; }
.col { flex: 1; min-width: 0; }

.significant {
  border: 1px solid rgba(255, 196, 120, .28);
  background: rgba(255, 196, 120, .04);
  border-radius: 12px;
  padding: 16px 16px 2px;
  margin-top: 4px;
}
.modal .significant-head { color: var(--text); font-size: 14px; margin-bottom: 14px; }
.significant-head .note { display: block; }

.affected {
  margin: 12px 0 4px;
  padding-left: 18px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text);
}

.modal .form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 12px 0 0;
}

.btn:disabled { opacity: .55; cursor: progress; }

@media (max-width: 600px) {
  .modal { padding: 22px 18px; }
  .row { flex-direction: column; gap: 0; }
}
</style>
