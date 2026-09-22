<template>
  <div class="activity-log glass">
    <div class="log-header">
      <span class="eyebrow">Activity log</span>
      <button type="button" class="btn btn-ghost small" @click="$emit('close')">Close</button>
    </div>

    <p v-if="loading" class="hint">Loading…</p>
    <p v-else-if="error" class="field-error">{{ error }}</p>
    <p v-else-if="!entries.length" class="hint">No changes recorded yet.</p>
    <ul v-else class="entries">
      <li v-for="entry in entries" :key="entry.logId" class="entry">
        <div class="entry-head">
          <span class="action" :class="entry.action">{{ entry.action }}</span>
          <span class="when">{{ formatWhen(entry.createdAt) }}</span>
        </div>
        <div class="who">by {{ describeActor(entry) }}</div>
        <ul v-if="Object.keys(entry.changes || {}).length" class="changes">
          <li v-for="(change, field) in entry.changes" :key="field" class="change-field">
            <strong>{{ fieldLabel(field) }}</strong>
            <ul class="change-lines">
              <li v-for="(d, i) in describeChange(entry.action, field, change)" :key="i" class="diff-row" :class="d.kind">
                <span v-if="d.label" class="diff-item-label">{{ d.label }}</span>
                <span v-if="d.kind === 'changed'" class="diff-values">
                  <span class="diff-old">{{ d.old }}</span>
                  <span class="diff-arrow" aria-hidden="true">→</span>
                  <span class="diff-new">{{ d.new }}</span>
                </span>
                <span v-else-if="d.kind === 'added'" class="diff-values">
                  <span class="diff-tag add" aria-hidden="true">+</span>
                  <span class="diff-new">{{ d.new }}</span>
                </span>
                <span v-else-if="d.kind === 'removed'" class="diff-values">
                  <span class="diff-tag remove" aria-hidden="true">−</span>
                  <span class="diff-old">{{ d.old }}</span>
                </span>
                <span v-else class="diff-values"><span class="diff-new">{{ d.new }}</span></span>
              </li>
            </ul>
          </li>
        </ul>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getVenueActivityLog } from '../../api/venueService.js'
import { roles } from '../../config/roles.js'

const props = defineProps({
  venueId: { type: String, required: true },
})
defineEmits(['close'])

const entries = ref([])
const loading = ref(true)
const error = ref('')

// createdAt comes back as a naive UTC timestamp with no "Z"/offset, and the
// venue is in Singapore, so the log always renders in Singapore time
// regardless of the viewer's own device/browser timezone, rather than
// silently using whatever local timezone happens to be set (which is also
// what native Date parsing of a bare ISO string like this would otherwise
// misinterpret as *already local*, not UTC).
function formatWhen(iso) {
  const withZone = /Z|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`
  return new Date(withZone).toLocaleString('en-SG', {
    timeZone: 'Asia/Singapore',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }) + ' SGT'
}

function describeActor(entry) {
  const roleLabel = roles[entry.changedByRole]?.label || entry.changedByRole || 'unknown role'
  const name = entry.changedByName || entry.changedBy
  return `${name} (${roleLabel})`
}

const FIELD_LABELS = {
  code: 'Code',
  name: 'Name',
  location: 'Location',
  address: 'Address',
  floor: 'Floor',
  description: 'Description',
  facilities: 'Facilities',
  accessibility: 'Accessibility',
  layouts: 'Supported layouts',
  operatingHours: 'Operating hours',
  turnaroundMinutes: 'Turnaround (minutes)',
  isActive: 'Active',
}
const SUB_FIELD_LABELS = { opens: 'opening time', closes: 'closing time', capacity: 'capacity' }
const FULL_DAY_NAMES = {
  Mon: 'Monday', Tue: 'Tuesday', Wed: 'Wednesday', Thu: 'Thursday',
  Fri: 'Friday', Sat: 'Saturday', Sun: 'Sunday',
}

function fieldLabel(field) {
  return FIELD_LABELS[field] || field
}

// Renders a raw field value the same friendly way the venue detail panel
// does, instead of dumping its JSON. A list of layout objects or operating
// hours is unreadable as raw JSON to a non-technical Venue Staff user. Used
// for the one-shot "created" snapshot and for plain scalar field values.
function formatValue(field, value) {
  if (value === null || value === undefined || value === '') return '(empty)'
  if (field === 'layouts') {
    return value.length ? value.map((l) => `${l.name} (${l.capacity})`).join(', ') : '(none)'
  }
  if (field === 'operatingHours') {
    return value.length ? value.map((h) => `${h.day} ${h.opens}–${h.closes}`).join(', ') : '(none, closed every day)'
  }
  if (field === 'facilities' || field === 'accessibility') {
    return value.length ? value.join(', ') : '(none)'
  }
  if (field === 'isActive') return value ? 'Active' : 'Retired'
  return String(value)
}

function describeAddedRemoved(field, item) {
  if (field === 'operatingHours') return `${item.opens}–${item.closes}`
  if (field === 'layouts') return `capacity ${item.capacity}`
  return JSON.stringify(item)
}

// Each returned entry is a structured diff row, { kind, label, old, new },
// not a pre-formatted sentence, so the template can render old and new
// with genuinely distinct styling (a muted pill vs. a bold highlight)
// instead of a flowing "was changed from X to Y" line that reads as one
// flat block of text and hides exactly which part is the change.
function describeChange(action, field, change) {
  if (action === 'created') return [{ kind: 'set', label: null, new: formatValue(field, change) }]

  if (field === 'operatingHours' || field === 'layouts') {
    const itemLabel = field === 'operatingHours' ? (k) => FULL_DAY_NAMES[k] || k : (k) => k
    const rows = []
    for (const [key, itemDiff] of Object.entries(change)) {
      const label = itemLabel(key)
      if (itemDiff.added) {
        rows.push({ kind: 'added', label, new: describeAddedRemoved(field, itemDiff.added) })
      } else if (itemDiff.removed) {
        rows.push({ kind: 'removed', label, old: describeAddedRemoved(field, itemDiff.removed) })
      } else {
        for (const [subField, subChange] of Object.entries(itemDiff)) {
          const subLabel = SUB_FIELD_LABELS[subField] || subField
          rows.push({ kind: 'changed', label: `${label}'s ${subLabel}`, old: subChange.old, new: subChange.new })
        }
      }
    }
    return rows
  }

  if (field === 'facilities' || field === 'accessibility') {
    const rows = []
    for (const item of change.added || []) rows.push({ kind: 'added', label: null, new: item })
    for (const item of change.removed || []) rows.push({ kind: 'removed', label: null, old: item })
    return rows
  }

  if (change && typeof change === 'object' && ('old' in change || 'new' in change)) {
    return [{ kind: 'changed', label: null, old: formatValue(field, change.old), new: formatValue(field, change.new) }]
  }
  return [{ kind: 'set', label: null, new: formatValue(field, change) }]
}

onMounted(async () => {
  try {
    const { data } = await getVenueActivityLog(props.venueId)
    entries.value = data
  } catch {
    error.value = 'Unable to load the activity log. Please try again.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.activity-log { border-radius: 16px; padding: 22px; margin-top: 16px; }
.log-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.hint { color: var(--muted); font-size: 13px; margin: 0; }
.field-error { color: #FF8A76; font-size: 13px; margin: 0; }

.entries { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 14px; }
.entry {
  border-left: 2px solid var(--hairline);
  padding-left: 14px;
}
.entry-head { display: flex; align-items: center; gap: 10px; }
.action {
  font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
  padding: 3px 9px; border-radius: 999px; font-weight: 600;
}
.action.created { background: rgba(56, 224, 200, .15); color: var(--signal); }
.action.updated { background: rgba(167, 139, 250, .18); color: var(--iris-soft); }
.action.retired { background: rgba(255, 138, 118, .15); color: #FF8A76; }
.when { font-size: 12px; color: var(--muted); }
.who { font-size: 12px; color: var(--muted); margin-top: 2px; }

.changes { list-style: none; margin: 8px 0 0; padding: 0; font-size: 13px; color: var(--text); }
.change-field { margin-top: 10px; }
.change-field:first-child { margin-top: 0; }
.change-lines { list-style: none; margin: 4px 0 0; padding: 0; }

.diff-row {
  margin-top: 6px;
  padding: 6px 10px;
  border-left: 2px solid var(--hairline);
  background: rgba(255, 255, 255, .015);
  border-radius: 0 6px 6px 0;
}
.diff-row.changed { border-left-color: rgba(167, 139, 250, .5); }
.diff-row.added { border-left-color: var(--signal); }
.diff-row.removed { border-left-color: #FF8A76; }

.diff-item-label {
  display: block;
  font-size: 11px;
  letter-spacing: .03em;
  color: var(--muted);
  margin-bottom: 2px;
}

.diff-values { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; font-size: 13px; }

.diff-old {
  color: var(--muted);
  background: rgba(255, 255, 255, .05);
  padding: 1px 7px;
  border-radius: 5px;
}
.diff-new {
  color: var(--signal);
  font-weight: 600;
}
.diff-arrow { color: var(--muted); font-size: 12px; }

.diff-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  flex-shrink: 0;
}
.diff-tag.add { background: rgba(56, 224, 200, .18); color: var(--signal); }
.diff-tag.remove { background: rgba(255, 138, 118, .18); color: #FF8A76; }
.diff-row.removed .diff-old { color: #FF8A76; background: rgba(255, 138, 118, .1); }

.btn.small { padding: 6px 14px; font-size: 12px; }
</style>
