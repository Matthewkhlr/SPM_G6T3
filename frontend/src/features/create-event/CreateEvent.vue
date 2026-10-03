<template>
  <div class="create-event">
    <!-- Success state — the created/submitted event, straight from the API response -->
    <div v-if="created" class="result-card">
      <h3>Event request submitted</h3>
      <p>
        <strong>{{ created.eventName }}</strong> was saved as a
        <span class="status-pill">{{ created.status }}</span>.
      </p>
      <p class="result-id">Reference: {{ created.eventId }}</p>
      <button class="btn btn-solid" @click="startAnother">Create another</button>
    </div>

    <form v-else class="form-card" @submit.prevent="submit">
      <p class="form-intro">
        Fields marked <span class="req">*</span> are required to submit — save a draft any time
        with just an event name.
      </p>
      <p v-if="editingEventId" class="draft-banner">Editing a saved draft.</p>

      <label for="eventName">Event name <span class="req">*</span></label>
      <input
        id="eventName"
        v-model.trim="form.eventName"
        type="text"
        placeholder="e.g. Q3 Partner Summit"
      />
      <p v-if="submitted && !form.eventName" class="field-error">Event name is required.</p>

      <div class="row">
        <div class="col">
          <label for="proposedStartAt">Starts <span class="req">*</span></label>
          <input id="proposedStartAt" v-model="form.proposedStartAt" type="datetime-local" />
          <p v-if="submitted && !form.proposedStartAt" class="field-error">Start date is required.</p>
        </div>
        <div class="col">
          <label for="proposedEndAt">Ends <span class="req">*</span></label>
          <input id="proposedEndAt" v-model="form.proposedEndAt" type="datetime-local" />
          <p v-if="submitted && !form.proposedEndAt" class="field-error">End date is required.</p>
          <p v-else-if="submitted && endBeforeStart" class="field-error">
            End must be after the start.
          </p>
        </div>
      </div>

      <div class="row">
        <div class="col">
          <label for="expectedAttendance">Expected attendance <span class="req">*</span></label>
          <input id="expectedAttendance" v-model.number="form.expectedAttendance" type="number" min="0" />
          <p v-if="submitted && !isValidAttendance" class="field-error">
            Enter an attendance of 0 or more.
          </p>
        </div>
        <div class="col">
          <label for="category">Category</label>
          <select id="category" v-model="form.category">
            <option :value="null">Not specified</option>
            <option v-for="option in categories" :key="option" :value="option">{{ option }}</option>
          </select>
        </div>
      </div>

      <label for="purpose">Purpose</label>
      <input id="purpose" v-model.trim="form.purpose" type="text" placeholder="What is this event for?" />

      <label for="description">Description</label>
      <textarea
        id="description"
        v-model.trim="form.description"
        rows="3"
        placeholder="Any extra detail a coordinator should know"
      ></textarea>

      <label for="venueRequirements">Venue requirements</label>
      <input
        id="venueRequirements"
        v-model.trim="form.venueRequirements"
        type="text"
        placeholder="e.g. Large hall with a stage"
      />

      <label for="equipmentRequirements">Equipment requirements</label>
      <input
        id="equipmentRequirements"
        v-model.trim="form.equipmentRequirements"
        type="text"
        placeholder="e.g. Projector and PA system"
      />

      <p v-if="error" class="form-error">{{ error }}</p>
      <p v-if="draftError" class="form-error">{{ draftError }}</p>
      <p v-if="draftSavedMessage" class="draft-saved">{{ draftSavedMessage }}</p>

      <div class="form-actions">
        <button
          class="btn btn-outline"
          type="button"
          :disabled="!form.eventName || draftSaving"
          @click="saveAsDraft"
        >
          {{ draftSaving ? 'Saving draft…' : 'Save as draft' }}
        </button>
        <button class="btn btn-solid" type="submit" :disabled="saving">
          {{ saving ? 'Saving…' : 'Create event request' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { createEvent, getEvent, saveDraft, submitDraft, updateDraft } from '../../api/eventService.js'
import { consumeEditingId, setDirty } from '../../store/draftEditor.js'

const categories = ['conference', 'workshop', 'networking', 'meeting']

function blankForm() {
  return {
    eventName: '',
    purpose: '',
    description: '',
    category: null,
    proposedStartAt: '',
    proposedEndAt: '',
    expectedAttendance: null,
    venueRequirements: '',
    equipmentRequirements: ''
  }
}

// datetime-local inputs need "YYYY-MM-DDTHH:mm"; the API returns full ISO
// strings (or null, for a draft that never got that far).
function toInputDatetime(iso) {
  return iso ? iso.slice(0, 16) : ''
}

// The reverse: an empty input must become null, not "", to satisfy the
// backend's Optional[datetime] draft schema.
function toPayloadDatetime(value) {
  return value || null
}

const form = reactive(blankForm())
const submitted = ref(false)
const saving = ref(false)
const error = ref('')
const created = ref(null)

const editingEventId = ref(null)
const draftSaving = ref(false)
const draftSavedMessage = ref('')
const draftError = ref('')
const lastSaved = ref('')

const isValidAttendance = computed(
  () => typeof form.expectedAttendance === 'number' && form.expectedAttendance >= 0
)
const endBeforeStart = computed(
  () =>
    !!form.proposedStartAt &&
    !!form.proposedEndAt &&
    new Date(form.proposedEndAt) <= new Date(form.proposedStartAt)
)

const isValid = computed(
  () =>
    !!form.eventName &&
    !!form.proposedStartAt &&
    !!form.proposedEndAt &&
    !endBeforeStart.value &&
    isValidAttendance.value
)

const isDirty = computed(() => JSON.stringify(form) !== lastSaved.value)
watch(isDirty, (value) => setDirty(value), { immediate: true })

function markSaved() {
  lastSaved.value = JSON.stringify(form)
}

function populateFormFromEvent(data) {
  form.eventName = data.eventName || ''
  form.purpose = data.purpose || ''
  form.description = data.description || ''
  form.category = data.category ?? null
  form.proposedStartAt = toInputDatetime(data.proposedStartAt)
  form.proposedEndAt = toInputDatetime(data.proposedEndAt)
  form.expectedAttendance = data.expectedAttendance ?? null
  form.venueRequirements = data.venueRequirements || ''
  form.equipmentRequirements = data.equipmentRequirements || ''
}

function buildPayload() {
  return {
    eventName: form.eventName,
    purpose: form.purpose,
    description: form.description,
    category: form.category,
    proposedStartAt: toPayloadDatetime(form.proposedStartAt),
    proposedEndAt: toPayloadDatetime(form.proposedEndAt),
    expectedAttendance: form.expectedAttendance,
    venueRequirements: form.venueRequirements,
    equipmentRequirements: form.equipmentRequirements
  }
}

function handleBeforeUnload(event) {
  if (isDirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}

function startAnother() {
  Object.assign(form, blankForm())
  submitted.value = false
  error.value = ''
  created.value = null
  editingEventId.value = null
  draftSavedMessage.value = ''
  draftError.value = ''
  markSaved()
}

async function saveAsDraft() {
  draftError.value = ''
  draftSavedMessage.value = ''
  if (!form.eventName) return // Save as draft is disabled without a name (AC1); nothing else is required.

  draftSaving.value = true
  try {
    const { data } = editingEventId.value
      ? await updateDraft(editingEventId.value, buildPayload())
      : await saveDraft(buildPayload())
    editingEventId.value = data.eventId
    markSaved()
    draftSavedMessage.value = 'Draft saved.'
  } catch (err) {
    const detail = err.response?.data?.detail
    draftError.value = typeof detail === 'string' ? detail : 'Could not save the draft. Please try again.'
  } finally {
    draftSaving.value = false
  }
}

async function submit() {
  submitted.value = true
  error.value = ''
  // Mirrors the server's own rules so obvious mistakes don't cost a round trip;
  // the API re-validates everything regardless.
  if (!isValid.value) return

  saving.value = true
  try {
    const { data } = editingEventId.value
      ? await submitDraft(editingEventId.value, buildPayload())
      : await createEvent(buildPayload())
    created.value = data
    markSaved()
  } catch (err) {
    const detail = err.response?.data?.detail
    error.value =
      typeof detail === 'string'
        ? detail
        : 'Could not create the event request. Please try again.'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  const id = consumeEditingId()
  if (id) {
    try {
      const { data } = await getEvent(id)
      populateFormFromEvent(data)
      editingEventId.value = id
    } catch (err) {
      draftError.value = 'Could not load the draft. Please try again.'
    }
  }
  markSaved()
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  setDirty(false)
})
</script>

<style scoped>
.create-event { max-width: 620px; }

.form-card,
.result-card {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 26px 28px;
}

.form-intro { font-size: 13px; line-height: 1.7; color: var(--muted); margin: 0 0 14px; }
.draft-banner {
  font-size: 12px;
  color: var(--halo);
  background: rgba(124, 77, 255, .12);
  border: 1px dashed rgba(167, 139, 250, .35);
  border-radius: 9px;
  padding: 8px 12px;
  margin: 0 0 18px;
}
.req { color: var(--iris-soft); }

label {
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
  display: block;
  margin-bottom: 6px;
}

input,
select,
textarea {
  width: 100%;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  padding: 0 12px;
  height: 42px;
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--text);
  font-family: 'Inter', sans-serif;
  transition: border-color .35s var(--ease-out), box-shadow .35s var(--ease-out);
}
textarea { height: auto; padding: 11px 12px; resize: vertical; line-height: 1.6; }
input::placeholder, textarea::placeholder { color: rgba(203, 188, 240, .32); }
input:focus, select:focus, textarea:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .6);
  box-shadow: 0 0 0 3px rgba(124, 77, 255, .16);
}
select option { background: #150A30; color: var(--text); }

.row { display: flex; gap: 16px; }
.col { flex: 1; min-width: 0; }

.field-error { color: #FF8A76; font-size: 11px; margin: -12px 0 12px; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 4px 0 16px;
}
.draft-saved {
  color: var(--halo);
  font-size: 13px;
  background: rgba(124, 77, 255, .1);
  border: 1px solid rgba(167, 139, 250, .3);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 4px 0 16px;
}

.form-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 6px; }
.btn:disabled { opacity: .55; cursor: progress; transform: none; box-shadow: none; }

.result-card h3 { margin: 0 0 14px; font-size: 18px; font-weight: 500; }
.result-card p { font-size: 14px; line-height: 1.7; color: var(--body); margin: 0 0 10px; }
.result-id { font-size: 12px; color: var(--muted); margin-bottom: 22px !important; }
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

@media (max-width: 560px) {
  .row { flex-direction: column; gap: 0; }
  .form-actions { flex-direction: column-reverse; }
}
</style>
