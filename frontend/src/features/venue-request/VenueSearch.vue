<template>
  <form class="venue-search" data-testid="venue-search" @submit.prevent="search">
    <h3>Search venues for this event</h3>
    <p class="hint">Filled in from the event. Change anything, then search. Times are in UTC.</p>

    <div class="fields">
      <label>
        Starts (UTC)
        <input v-model="startsAt" type="datetime-local" data-testid="venue-search-starts" />
      </label>
      <label>
        Ends (UTC)
        <input v-model="endsAt" type="datetime-local" data-testid="venue-search-ends" />
      </label>
      <label>
        Expected attendance
        <input v-model.number="attendance" type="number" min="0" data-testid="venue-search-attendance" />
      </label>
      <label>
        Layout
        <select v-model="layout" data-testid="venue-search-layout">
          <option value="">Any layout</option>
          <option v-for="name in layoutOptions" :key="name" :value="name">{{ name }}</option>
        </select>
      </label>
      <label>
        Location
        <input v-model="location" type="text" placeholder="e.g. HarbourFront" data-testid="venue-search-location" />
      </label>
    </div>

    <fieldset v-if="facilityOptions.length">
      <legend>Required facilities</legend>
      <p v-if="event.venueRequirements" class="hint">This event asks for: {{ event.venueRequirements }}</p>
      <label v-for="name in facilityOptions" :key="name" class="check">
        <input v-model="facilities" type="checkbox" :value="name" :data-testid="`venue-search-facility-${name}`" />
        {{ name }}
      </label>
    </fieldset>

    <fieldset v-if="accessibilityOptions.length">
      <legend>Required accessibility features</legend>
      <p v-if="event.accessibilityNeeds" class="hint">This event needs: {{ event.accessibilityNeeds }}</p>
      <label v-for="name in accessibilityOptions" :key="name" class="check">
        <input
          v-model="accessibility"
          type="checkbox"
          :value="name"
          :data-testid="`venue-search-accessibility-${name}`"
        />
        {{ name }}
      </label>
    </fieldset>

    <div class="actions">
      <button type="submit" class="btn btn-solid small" :disabled="searching" data-testid="venue-search-submit">
        {{ searching ? 'Searching…' : 'Search venues' }}
      </button>
      <button
        v-if="active"
        type="button"
        class="btn btn-ghost small"
        data-testid="venue-search-reset"
        @click="reset"
      >
        Show all venues
      </button>
    </div>
    <p v-if="error" class="form-error" data-testid="venue-search-error">{{ error }}</p>
    <p v-else-if="active" class="hint" data-testid="venue-search-summary">{{ summary }}</p>
  </form>
</template>

<script setup>
import { computed, ref } from 'vue'
import { searchVenues } from '../../api/venueService.js'

const props = defineProps({
  event: { type: Object, required: true },
  venues: { type: Array, required: true },
})
const emit = defineEmits(['results'])

// datetime-local works without a timezone; the team reads every time as UTC.
function toInput(iso) {
  return iso ? iso.replace(/Z|[+-]\d\d:\d\d$/, '').slice(0, 16) : ''
}

function toUtc(value) {
  return value ? `${value}:00Z` : undefined
}

// The event's requirements are free text, so a venue's option counts as asked
// for when its name appears in that text (ignoring case and hyphens).
function normalise(text) {
  return (text || '').toLowerCase().replace(/-/g, ' ').replace(/\s+/g, ' ').trim()
}

function mentioned(options, text) {
  const wording = normalise(text)
  return options.filter((name) => wording.includes(normalise(name)))
}

function unique(lists) {
  return [...new Set(lists.flat().filter(Boolean))].sort((a, b) => a.localeCompare(b))
}

const facilityOptions = computed(() => unique(props.venues.map((v) => v.facilities || [])))
const accessibilityOptions = computed(() => unique(props.venues.map((v) => v.accessibility || [])))
const layoutOptions = computed(() =>
  unique([...props.venues.map((v) => (v.layouts || []).map((l) => l.name)), props.event.layoutPreference || '']),
)

// SPM-61 AC1: everything starts from the event's own requirements.
const startsAt = ref(toInput(props.event.proposedStartAt))
const endsAt = ref(toInput(props.event.proposedEndAt))
const attendance = ref(props.event.expectedAttendance || 0)
const layout = ref(props.event.layoutPreference || '')
const location = ref('')
const facilities = ref(mentioned(facilityOptions.value, props.event.venueRequirements))
const accessibility = ref(mentioned(accessibilityOptions.value, props.event.accessibilityNeeds))

const searching = ref(false)
const error = ref('')
const active = ref(false)
const found = ref(0)

const summary = computed(() =>
  found.value
    ? `${found.value} ${found.value === 1 ? 'venue fits' : 'venues fit'} these requirements.`
    : 'No venue fits these requirements. Try changing a filter.',
)

async function search() {
  searching.value = true
  error.value = ''
  try {
    const { data } = await searchVenues({
      eventId: props.event.eventId,
      startsAt: toUtc(startsAt.value),
      endsAt: toUtc(endsAt.value),
      minCapacity: Number(attendance.value) || 0,
      location: location.value.trim() || undefined,
      layout: layout.value || undefined,
      facility: facilities.value,
      accessibility: accessibility.value,
    })
    found.value = data.length
    active.value = true
    emit('results', data)
  } catch (err) {
    const detail = err.response?.data?.detail
    error.value = typeof detail === 'string'
      ? detail
      : 'Unable to search venues right now. Check the filters and try again.'
  } finally {
    searching.value = false
  }
}

function reset() {
  active.value = false
  error.value = ''
  emit('results', null)
}
</script>

<style scoped>
.venue-search {
  margin: 0 0 22px; padding: 18px; border-radius: 12px;
  background: var(--glass); border: 1px solid var(--hairline);
}
.venue-search h3 { margin: 0 0 4px; font-size: 15px; color: var(--text); }
.hint { font-size: 13px; color: var(--muted); margin: 0 0 12px; line-height: 1.6; }
.fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 12px 0; }
.fields label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--body); }
/* Same look as the notes box on this page. */
.fields input, .fields select {
  font: inherit; font-size: 13px; color: var(--text); color-scheme: dark;
  background: rgba(255, 255, 255, .03); border: 1px solid var(--hairline); border-radius: 9px; padding: 8px 10px;
}
.fields select option { background: var(--deep); color: var(--text); }
.check input { accent-color: var(--iris); }
fieldset { border: 0; padding: 0; margin: 0 0 12px; }
legend { font-size: 13px; color: var(--text); margin-bottom: 6px; }
.check { display: inline-flex; align-items: center; gap: 6px; margin: 0 14px 6px 0; font-size: 13px; color: var(--body); }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }
.form-error {
  margin: 12px 0 0; color: #FF8A76; font-size: 13px;
  background: rgba(255, 138, 118, .08); border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px; padding: 11px 14px;
}
.venue-search > .hint:last-child { margin: 12px 0 0; }
</style>
