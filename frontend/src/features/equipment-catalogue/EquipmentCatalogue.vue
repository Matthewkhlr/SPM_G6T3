<template>
  <div class="catalogue">
    <div class="toolbar">
      <input
        v-model="query"
        class="search"
        type="search"
        placeholder="Search by name, code, or location"
        aria-label="Search equipment"
      />
      <div class="filters">
        <label>
          Category
          <select v-model="category">
            <option value="all">All</option>
            <option v-for="name in categories" :key="name" :value="name">{{ sentenceCase(name) }}</option>
          </select>
        </label>
      </div>
      <p class="result-count">Showing {{ filtered.length }} of {{ items.length }}</p>
      <button v-if="canWrite" type="button" class="btn btn-outline add-btn" @click="startCreate">Add equipment</button>
    </div>

    <div class="body">
      <div class="item-list">
        <button
          v-for="item in filtered"
          :key="item.equipmentId"
          type="button"
          class="item-row"
          :class="{ active: selected?.equipmentId === item.equipmentId }"
          @click="selectItem(item.equipmentId)"
        >
          <span class="item-name">{{ titleCase(item.name) }}</span>
          <span class="item-meta">{{ item.code }} · {{ sentenceCase(item.category) }}</span>
          <span class="item-qty">{{ item.serviceableQuantity }}/{{ item.totalQuantity }}</span>
        </button>
        <p v-if="!loading && !error && !filtered.length" class="empty-list">No equipment matches this search.</p>
      </div>

      <EquipmentForm
        v-if="mode !== 'view'"
        :mode="mode"
        :equipment="mode === 'edit' ? selected : null"
        :warning="saveWarning"
        @save="onSave"
        @cancel="cancelEdit"
      />
      <div v-else-if="loading" class="item-detail empty">Loading equipment…</div>
      <div v-else-if="error" class="item-detail empty error">{{ error }}</div>
      <div v-else-if="selected" class="item-detail">
        <div class="detail-header">
          <h3>{{ titleCase(selected.name) }}</h3>
          <div class="detail-actions">
            <button v-if="canWrite" type="button" class="btn btn-ghost small" @click="startEdit">Edit</button>
            <button type="button" class="btn btn-ghost small" @click="showLog = !showLog">
              {{ showLog ? 'Hide log' : 'Activity log' }}
            </button>
            <span class="count-tag">{{ selected.serviceableQuantity }} serviceable</span>
          </div>
        </div>
        <dl>
          <dt>Code</dt><dd>{{ selected.code }}</dd>
          <dt>Category</dt><dd>{{ sentenceCase(selected.category) }}</dd>
          <dt>Description</dt><dd>{{ selected.description || "—" }}</dd>
          <dt>Home location</dt><dd>{{ selected.homeLocation || "—" }}</dd>
          <dt>Technical notes</dt><dd>{{ selected.technicalNotes || "—" }}</dd>
          <dt>Total owned</dt><dd>{{ selected.totalQuantity }}</dd>
          <dt>Damaged</dt><dd>{{ selected.outOfService.damaged }}</dd>
          <dt>Under maintenance</dt><dd>{{ selected.outOfService.maintenance }}</dd>
          <dt>Retired</dt><dd>{{ selected.outOfService.retired }}</dd>
          <dt>Serviceable</dt><dd>{{ selected.serviceableQuantity }}</dd>
        </dl>
        <form class="availability" @submit.prevent="checkWindow">
          <label>From<input v-model="windowStart" type="datetime-local" required /></label>
          <label>Until<input v-model="windowEnd" type="datetime-local" required /></label>
          <button type="submit" class="btn btn-ghost small">Check available</button>
          <p v-if="availableForWindow !== null" class="available-result">{{ availableForWindow }} available in this period</p>
        </form>
        <EquipmentActivityLog v-if="showLog" :equipment-id="selected.equipmentId" />
      </div>
      <div v-else class="item-detail empty">No equipment in the catalogue yet.</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  checkEquipmentAvailability,
  createEquipment,
  getEquipment,
  getEquipmentList,
  updateEquipment,
} from '../../api/equipmentService.js'
import { session } from '../../store/session.js'
import EquipmentForm from './EquipmentForm.vue'
import EquipmentActivityLog from './EquipmentActivityLog.vue'

const items = ref([])
const selected = ref(null)
const loading = ref(true)
const error = ref('')
const query = ref('')
const category = ref('all')
const mode = ref('view')
const showLog = ref(false)
const saveWarning = ref('')
const windowStart = ref('')
const windowEnd = ref('')
const availableForWindow = ref(null)
const canWrite = computed(() => session.role === 'techsupport')
let actionToken = 0

function sentenceCase(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function titleCase(value) {
  return String(value || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => {
      if (/[0-9]/.test(word) || word === word.toUpperCase()) return word
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    })
    .join(' ')
}

const categories = computed(() =>
  [...new Set(items.value.map((item) => item.category).filter(Boolean))].sort()
)

const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return items.value.filter((item) => {
    if (category.value !== 'all' && item.category !== category.value) return false
    if (!needle) return true
    return [item.name, item.code, item.homeLocation, item.category]
      .join(' ')
      .toLowerCase()
      .includes(needle)
  })
})

async function refreshList() {
  const { data } = await getEquipmentList()
  items.value = data
}

async function selectItem(equipmentId) {
  const token = ++actionToken
  try {
    error.value = ''
    mode.value = 'view'
    showLog.value = false
    saveWarning.value = ''
    availableForWindow.value = null
    const { data } = await getEquipment(equipmentId)
    if (token !== actionToken) return
    selected.value = data
  } catch {
    if (token === actionToken) error.value = 'Unable to load this equipment. Please try again.'
  }
}

function startCreate() {
  mode.value = 'create'
  saveWarning.value = ''
  showLog.value = false
}

function startEdit() {
  mode.value = 'edit'
  saveWarning.value = ''
}

function cancelEdit() {
  mode.value = 'view'
  saveWarning.value = ''
}

async function onSave(payload) {
  try {
    saveWarning.value = ''
    const saved = mode.value === 'create'
      ? (await createEquipment(payload)).data
      : (await updateEquipment(selected.value.equipmentId, payload)).data
    await refreshList()
    mode.value = 'view'
    await selectItem(saved.equipmentId)
  } catch (err) {
    const status = err.response?.status
    const detail = err.response?.data?.detail
    if (status === 409 || status === 422) {
      saveWarning.value = typeof detail === 'string' ? detail : 'This change could not be saved.'
      return
    }
    error.value = 'Unable to save this equipment. Please try again.'
  }
}

async function checkWindow() {
  if (!selected.value) return
  try {
    const { data } = await checkEquipmentAvailability({
      equipmentId: selected.value.equipmentId,
      startsAt: new Date(windowStart.value).toISOString(),
      endsAt: new Date(windowEnd.value).toISOString(),
    })
    availableForWindow.value = data.availableQuantity
  } catch {
    error.value = 'Unable to check availability for that period.'
  }
}

onMounted(async () => {
  try {
    await refreshList()
    if (items.value.length) await selectItem(items.value[0].equipmentId)
  } catch {
    error.value = 'Unable to load the equipment catalogue. Please try again.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.catalogue { display: flex; flex-direction: column; gap: 16px; }

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 12px 16px;
}
.search {
  flex: 1 1 220px;
  min-width: 0;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 12px;
  color: var(--text);
  font: inherit;
  font-size: 14px;
  padding: 10px 14px;
}
.search::placeholder { color: var(--muted); }
.filters { display: flex; flex-wrap: wrap; gap: 12px; }
.filters label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--muted);
}
.filters select {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 12px;
  color: var(--text);
  font: inherit;
  font-size: 13px;
  letter-spacing: 0;
  text-transform: none;
  padding: 8px 12px;
  min-width: 160px;
}
.filters select option {
  color: #1b1230;
  background: #ffffff;
}
.result-count { margin: 0 0 8px auto; font-size: 12px; color: var(--muted); }

.body { display: grid; grid-template-columns: minmax(240px, 340px) 1fr; gap: 20px; align-items: start; }

.item-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: min(640px, calc(100vh - 240px));
  overflow: auto;
  padding-right: 4px;
}
.item-row {
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto auto;
  column-gap: 10px;
  text-align: left;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 12px;
  padding: 10px 12px;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.item-row:hover { background: var(--glass-strong); }
.item-row.active {
  border-color: rgba(167, 139, 250, .55);
  background: linear-gradient(90deg, rgba(124, 77, 255, .22), rgba(124, 77, 255, .04));
}
.item-name {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 500;
  color: var(--text);
  font-size: 14px;
}
.item-meta { grid-column: 1; font-size: 12px; color: var(--muted); }
.item-qty {
  grid-row: 1 / span 2;
  grid-column: 2;
  align-self: center;
  font-size: 12px;
  color: var(--body);
}
.empty-list { margin: 8px 4px; font-size: 13px; color: var(--muted); }

.item-detail {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 16px;
  padding: 26px;
}
.item-detail.empty { display: flex; align-items: center; justify-content: center; color: var(--muted); min-height: 180px; }
.item-detail.error { color: #FF8A76; }
.item-detail h3 { margin: 0; font-size: 19px; font-weight: 500; }
dl { margin: 0; display: grid; grid-template-columns: 160px 1fr; row-gap: 12px; }
dt { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); align-self: center; }
dd { margin: 0; font-size: 14px; line-height: 1.6; color: var(--body); }

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  gap: 12px;
}
.detail-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.add-btn { margin-bottom: 8px; }
.availability {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 10px;
  margin-top: 18px;
}
.availability label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.availability input {
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: 10px;
  color: var(--text);
  font: inherit;
  font-size: 13px;
  padding: 8px 10px;
}
.available-result { margin: 0; font-size: 13px; color: var(--text); }
.count-tag {
  font-size: 11px;
  letter-spacing: .04em;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--iris-soft);
  background: rgba(124, 77, 255, .16);
  padding: 4px 10px;
  border-radius: 999px;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .body { grid-template-columns: 1fr; }
  .result-count { margin-left: 0; }
  .item-list { max-height: 280px; }
}
</style>
