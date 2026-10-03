<template>
  <form class="venue-form glass" @submit.prevent="submit" novalidate>
    <h3>{{ mode === 'create' ? 'Add venue' : 'Edit venue' }}</h3>

    <div class="field-grid">
      <div class="field">
        <label for="vf-code">Code (suggested from Name, feel free to change it)</label>
        <input id="vf-code" v-model="form.code" type="text" placeholder="e.g. MH-A" @input="codeEditedByUser = true" />
      </div>
      <div class="field">
        <label for="vf-name">Name</label>
        <input id="vf-name" v-model="form.name" type="text" required />
      </div>
      <div class="field">
        <label for="vf-location">Location (building or complex name)</label>
        <input id="vf-location" v-model="form.location" type="text" placeholder="e.g. HarbourFront Centre" required />
      </div>
      <div class="field">
        <label for="vf-address">Address (full street address)</label>
        <input id="vf-address" v-model="form.address" type="text" placeholder="e.g. 1 HarbourFront Walk, Singapore 098585" />
      </div>
      <div class="field">
        <label for="vf-floor">Floor</label>
        <input id="vf-floor" v-model="form.floor" type="text" placeholder="e.g. 2" />
      </div>
      <div class="field">
        <label for="vf-turnaround">Turnaround (minutes)</label>
        <input id="vf-turnaround" v-model.number="form.turnaroundMinutes" type="number" min="0" />
      </div>
    </div>

    <div class="field">
      <label for="vf-description">Description</label>
      <textarea id="vf-description" v-model="form.description" rows="2"></textarea>
    </div>

    <div class="field-grid">
      <div class="field">
        <label for="vf-facilities">Facilities (comma-separated)</label>
        <input id="vf-facilities" v-model="facilitiesText" type="text" placeholder="Projector, Whiteboard" />
      </div>
      <div class="field">
        <label for="vf-accessibility">Accessibility (comma-separated)</label>
        <input id="vf-accessibility" v-model="accessibilityText" type="text" placeholder="Wheelchair accessible" />
      </div>
    </div>

    <div class="repeat-section">
      <div class="repeat-header">
        <span class="eyebrow">Supported layouts</span>
        <button type="button" class="btn btn-ghost small" @click="addLayout">+ Add layout</button>
      </div>
      <div v-for="(layout, i) in form.layouts" :key="i" class="layout-block">
        <div class="repeat-row layout-row">
          <select v-model="layout.layoutType">
            <option value="" disabled>Select a layout type...</option>
            <option v-for="t in LAYOUT_TYPES" :key="t" :value="t">{{ t }}</option>
            <option :value="OTHER_LAYOUT">Other (please specify)</option>
          </select>
          <input v-model.number="layout.capacity" type="number" min="1" placeholder="Capacity" />
          <button type="button" class="btn btn-ghost small danger" @click="form.layouts.splice(i, 1)">Remove</button>
        </div>
        <input
          v-if="layout.layoutType === OTHER_LAYOUT"
          v-model="layout.customName"
          type="text"
          class="other-name-input"
          placeholder="Enter the custom layout name"
        />
      </div>
      <p v-if="!form.layouts.length" class="hint">No layouts yet, so capacity will show as 0.</p>
    </div>

    <div class="repeat-section">
      <div class="repeat-header">
        <span class="eyebrow">Operating hours</span>
        <button type="button" class="btn btn-ghost small" @click="addHours">+ Add day</button>
      </div>
      <div
        v-for="(hours, i) in form.operatingHours"
        :key="i"
        class="repeat-row hours-row"
        :class="{ 'has-error': duplicateDays.has(hours.day) }"
      >
        <select v-model="hours.day">
          <option v-for="d in DAYS" :key="d" :value="d">{{ d }}</option>
        </select>
        <input v-model="hours.opens" type="time" />
        <input v-model="hours.closes" type="time" />
        <button type="button" class="btn btn-ghost small danger" @click="form.operatingHours.splice(i, 1)">Remove</button>
      </div>
      <p v-if="!form.operatingHours.length" class="hint">No hours set, so the venue will show as closed every day.</p>
      <p v-if="duplicateDays.size" class="field-error">
        {{ [...duplicateDays].join(', ') }} {{ duplicateDays.size > 1 ? 'are' : 'is' }} listed more than once.
        Each day can only have one opening/closing time. Remove or change the duplicate row above before saving.
      </p>
    </div>

    <p v-if="errorMessage" class="field-error">{{ errorMessage }}</p>

    <div class="actions">
      <button type="button" class="btn btn-ghost" @click="$emit('cancel')" :disabled="submitting">Cancel</button>
      <button type="submit" class="btn btn-solid" :disabled="submitting">
        {{ submitting ? 'Saving…' : (mode === 'create' ? 'Create venue' : 'Save changes') }}
      </button>
    </div>
  </form>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { createVenue, updateVenue } from '../../api/venueService.js'

const props = defineProps({
  mode: { type: String, required: true }, // 'create' | 'edit'
  venue: { type: Object, default: null },
})
const emit = defineEmits(['saved', 'cancel'])

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

// The customer said layouts can be "classroom, theatre, boardroom, banquet,
// exhibition, or another arrangement" and that the team could "suggest your
// own list" -- so this is a guided dropdown of the common real-world
// options, not a hard restriction. OTHER_LAYOUT is a sentinel select value
// (never sent to the backend) that reveals a free-text field instead.
const LAYOUT_TYPES = [
  'Theatre', 'Classroom', 'Boardroom', 'U-Shape', 'Hollow Square',
  'Banquet', 'Cabaret', 'Exhibition', 'Reception / Cocktail', 'Herringbone',
  'Auditorium', 'Workshop / Breakout Pods',
]
const OTHER_LAYOUT = '__other__'

function toLayoutFormRow(layout) {
  const isPreset = LAYOUT_TYPES.includes(layout.name)
  return {
    layoutType: isPreset ? layout.name : OTHER_LAYOUT,
    customName: isPreset ? '' : layout.name,
    capacity: layout.capacity,
  }
}

const form = reactive({
  code: props.venue?.code ?? '',
  name: props.venue?.name ?? '',
  location: props.venue?.location ?? '',
  address: props.venue?.address ?? '',
  floor: props.venue?.floor ?? '',
  description: props.venue?.description ?? '',
  turnaroundMinutes: props.venue?.turnaroundMinutes ?? 0,
  layouts: props.venue ? props.venue.layouts.map(toLayoutFormRow) : [],
  operatingHours: props.venue ? props.venue.operatingHours.map((h) => ({ ...h })) : [],
})

const facilitiesText = ref((props.venue?.facilities ?? []).join(', '))
const accessibilityText = ref((props.venue?.accessibility ?? []).join(', '))

// Codes aren't defined anywhere in the spec as manual-only or system-
// generated, so this offers a sensible default without forcing it: while
// creating a new venue, the Code field is live-suggested from Name (and
// Floor as a fallback suffix) until the user actually types in that field
// themselves, at which point their input always wins and the suggestion
// stops. Editing an existing venue never touches its real code this way.
const codeEditedByUser = ref(props.mode === 'edit')

function suggestCode(name, floor) {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (!words.length) return ''
  const last = words[words.length - 1]
  const isTrailingTag = /^\d+$/.test(last) || /^[A-Za-z]$/.test(last)
  const initialsFrom = isTrailingTag ? words.slice(0, -1) : words
  const prefix = (initialsFrom.length ? initialsFrom : words).map((w) => w[0]).join('').toUpperCase()
  const suffix = isTrailingTag ? last.toUpperCase() : floor.trim()
  return suffix ? `${prefix}-${suffix}` : prefix
}

watch([() => form.name, () => form.floor], ([name, floor]) => {
  if (props.mode === 'create' && !codeEditedByUser.value) {
    form.code = suggestCode(name, floor)
  }
})

const submitting = ref(false)
const errorMessage = ref('')

// Each day should only appear once. A venue has one opening/closing time
// per day, not several conflicting ranges for the same day.
const duplicateDays = computed(() => {
  const seen = new Set()
  const dupes = new Set()
  for (const h of form.operatingHours) {
    if (seen.has(h.day)) dupes.add(h.day)
    seen.add(h.day)
  }
  return dupes
})

function addLayout() {
  form.layouts.push({ layoutType: '', customName: '', capacity: 1 })
}

// The actual layout name to submit: the dropdown's own value, or the
// typed-in text when "Other" was chosen.
function resolveLayoutName(layout) {
  return layout.layoutType === OTHER_LAYOUT ? layout.customName.trim() : layout.layoutType
}

// Every layout row needs an actual type chosen, and if that type is
// "Other" its custom name can't be left blank -- both checked client-side
// with plain-language wording before ever reaching the server.
const layoutIssues = computed(() => {
  const issues = []
  form.layouts.forEach((layout, i) => {
    if (!layout.layoutType) {
      issues.push(`Layout #${i + 1} needs a layout type selected.`)
    } else if (layout.layoutType === OTHER_LAYOUT && !layout.customName.trim()) {
      issues.push(`Layout #${i + 1} is set to "Other" but has no name entered.`)
    }
  })
  return issues
})
function addHours() {
  const usedDays = new Set(form.operatingHours.map((h) => h.day))
  const nextDay = DAYS.find((d) => !usedDays.has(d)) ?? DAYS[0]
  form.operatingHours.push({ day: nextDay, opens: '09:00', closes: '17:00' })
}

function toList(text) {
  return text.split(',').map((s) => s.trim()).filter(Boolean)
}

const TOP_LEVEL_FIELD_NAMES = {
  code: 'Code', name: 'Name', location: 'Location', address: 'Address', floor: 'Floor',
  description: 'Description', facilities: 'Facilities', accessibility: 'Accessibility',
  turnaroundMinutes: 'Turnaround (minutes)',
}

// Translates one raw FastAPI/Pydantic validation error (e.g. loc
// ["body", "layouts", 0, "capacity"], msg "Input should be greater than
// 0") into a sentence a non-technical Venue Staff user can act on, naming
// the actual layout or day involved instead of a bare field path like
// "body.layouts.0.capacity: Input should be greater than 0".
function describeValidationError(d) {
  const loc = (d.loc || []).filter((p) => p !== 'body')
  const msg = /greater than 0/.test(d.msg) ? 'must be greater than 0'
    : /at least 1 character/.test(d.msg) ? 'cannot be empty'
    : d.msg

  if (loc[0] === 'layouts' && typeof loc[1] === 'number') {
    const layout = form.layouts[loc[1]]
    const layoutName = layout ? resolveLayoutName(layout) : ''
    const ref = layoutName ? `The "${layoutName}" layout's` : `Layout #${loc[1] + 1}'s`
    const subField = loc[2] === 'capacity' ? 'capacity' : loc[2] === 'name' ? 'name' : loc[2]
    return `${ref} ${subField} ${msg}.`
  }
  if (loc[0] === 'operatingHours' && typeof loc[1] === 'number') {
    const hours = form.operatingHours[loc[1]]
    const ref = hours?.day ? `${hours.day}'s` : `Operating hours row #${loc[1] + 1}'s`
    return `${ref} ${loc[2] || 'entry'} ${msg}.`
  }
  const label = TOP_LEVEL_FIELD_NAMES[loc[0]] || loc[0] || 'This field'
  return `${label} ${msg}.`
}

function extractErrorMessage(err) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map(describeValidationError).join(' ')
  }
  return 'Something went wrong saving this venue. Please check the fields and try again.'
}

async function submit() {
  errorMessage.value = ''
  if (layoutIssues.value.length) {
    errorMessage.value = layoutIssues.value.join(' ')
    return
  }
  if (duplicateDays.value.size) {
    errorMessage.value = `${[...duplicateDays.value].join(', ')} ${duplicateDays.value.size > 1 ? 'are' : 'is'} listed more than once in operating hours. Remove or change the duplicate before saving.`
    return
  }
  submitting.value = true
  try {
    const payload = {
      code: form.code,
      name: form.name,
      location: form.location,
      address: form.address,
      floor: form.floor,
      description: form.description,
      turnaroundMinutes: form.turnaroundMinutes,
      facilities: toList(facilitiesText.value),
      accessibility: toList(accessibilityText.value),
      layouts: form.layouts.map((l) => ({ name: resolveLayoutName(l), capacity: Number(l.capacity) })),
      operatingHours: form.operatingHours.map((h) => ({ day: h.day, opens: h.opens, closes: h.closes })),
    }
    if (props.mode === 'create') {
      const { data } = await createVenue(payload)
      emit('saved', data)
    } else {
      const { data } = await updateVenue(props.venue.venueId, payload)
      emit('saved', data)
    }
  } catch (err) {
    errorMessage.value = extractErrorMessage(err)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.venue-form {
  border-radius: 16px;
  padding: 26px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.venue-form h3 { margin: 0; font-size: 19px; font-weight: 500; }

.field-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label {
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted);
}
.field input, .field textarea, .venue-form select {
  background: rgba(255, 255, 255, .03);
  border: 1px solid var(--hairline);
  border-radius: 8px;
  padding: 9px 12px;
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
}
.field input:focus, .field textarea:focus, .venue-form select:focus, .venue-form input:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .55);
}

.repeat-section { display: flex; flex-direction: column; gap: 10px; }
.repeat-header { display: flex; align-items: center; justify-content: space-between; }
.repeat-row {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 10px;
  align-items: center;
}
.repeat-row input, .repeat-row select {
  background: rgba(255, 255, 255, .03);
  border: 1px solid var(--hairline);
  border-radius: 8px;
  padding: 8px 10px;
  color: var(--text);
  font-size: 13px;
}
/* The closed <select> can be themed, but its open dropdown list is
   rendered by the browser/OS with its own (usually white) background --
   without this, the light theme text colour above becomes near-invisible
   on that white popup. Setting color/background directly on <option>
   fixes contrast in the popup across Chrome, Edge and Firefox. */
.venue-form option {
  background: #1A1030;
  color: #F3EEFF;
}
.hours-row { grid-template-columns: 100px 1fr 1fr auto; }
.hours-row.has-error select, .hours-row.has-error input {
  border-color: rgba(255, 138, 118, .6);
}
.layout-block { display: flex; flex-direction: column; gap: 8px; }
.layout-row { grid-template-columns: 1fr 1fr auto; }
.other-name-input {
  background: rgba(255, 255, 255, .03);
  border: 1px solid var(--hairline);
  border-radius: 8px;
  padding: 8px 10px;
  color: var(--text);
  font-size: 13px;
}
.hint { font-size: 12px; color: var(--muted); margin: 0; }

.btn.small { padding: 6px 14px; font-size: 12px; }
.btn.danger { color: #FF8A76; }

.field-error { color: #FF8A76; font-size: 13px; margin: 0; }

.actions { display: flex; justify-content: flex-end; gap: 10px; }

@media (max-width: 720px) {
  .field-grid { grid-template-columns: 1fr; }
  .hours-row { grid-template-columns: 1fr; }
}
</style>
