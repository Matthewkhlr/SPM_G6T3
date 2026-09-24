<template>
  <div class="catalogue">
    <div class="venue-list">
      <button v-if="canWrite" type="button" class="btn btn-outline add-btn" @click="startCreate">
        + Add venue
      </button>
      <label class="show-retired">
        <input type="checkbox" v-model="showRetired" @change="onToggleRetired" />
        Show retired venues
      </label>
      <div
        v-for="venue in venues"
        :key="venue.venueId"
        class="venue-row"
        :class="{ active: selected?.venueId === venue.venueId, retired: !venue.isActive }"
        @click="selectVenue(venue.venueId)"
      >
        <div class="venue-name">
          {{ venue.name }}
          <span v-if="!venue.isActive" class="retired-tag">Retired</span>
        </div>
        <div class="venue-meta">{{ venue.location }} · Capacity {{ venue.capacity }}</div>
      </div>
    </div>

    <div v-if="mode === 'create'">
      <VenueForm mode="create" @saved="onCreated" @cancel="mode = 'view'" />
    </div>
    <div v-else-if="mode === 'edit' && selected">
      <VenueForm mode="edit" :venue="selected" @saved="onEdited" @cancel="mode = 'view'" />
    </div>
    <div v-else>
      <div v-if="loading" class="venue-detail empty">Loading venues…</div>
      <div v-else-if="error" class="venue-detail empty error">{{ error }}</div>
      <div class="venue-detail" v-else-if="selected">
        <div class="detail-header">
          <h3>
            {{ selected.name }}
            <span v-if="!selected.isActive" class="retired-tag">Retired</span>
          </h3>
          <div class="detail-actions">
            <template v-if="canWrite && selected.isActive">
              <button type="button" class="btn btn-ghost small" @click="startEdit">Edit</button>
              <button type="button" class="btn btn-ghost small" @click="showLog = !showLog">
                {{ showLog ? 'Hide log' : 'Activity log' }}
              </button>
              <button type="button" class="btn btn-ghost small danger" @click="startRetire">Retire</button>
            </template>
            <button v-else type="button" class="btn btn-ghost small" @click="showLog = !showLog">
              {{ showLog ? 'Hide log' : 'Activity log' }}
            </button>
          </div>
        </div>
        <dl>
          <dt>Code</dt><dd>{{ selected.code }}</dd>
          <dt>Location</dt><dd>{{ selected.location }}</dd>
          <dt>Address</dt><dd>{{ selected.address }}, Level {{ selected.floor }}</dd>
          <dt>Description</dt><dd>{{ selected.description }}</dd>
          <dt>Capacity</dt><dd>{{ selected.capacity }} people</dd>
          <dt>Facilities</dt><dd>{{ selected.facilities.join(', ') }}</dd>
          <dt>Accessibility</dt><dd>{{ selected.accessibility.join(', ') }}</dd>
          <dt>Supported layouts</dt>
          <dd>{{ selected.layouts.map(l => `${l.name} (${l.capacity})`).join(', ') }}</dd>
          <dt>Operating hours</dt>
          <dd>{{ selected.operatingHours.map(h => `${h.day} ${h.opens}–${h.closes}`).join(', ') }}</dd>
          <dt>Turnaround needed</dt><dd>{{ selected.turnaroundMinutes }} minutes between bookings</dd>
        </dl>

        <div v-if="confirmingRetire" class="retire-warning">
          <p>Retire "{{ selected.name }}"? It will be hidden from the catalogue's default list (Venue Staff can
            still find it with "Show retired venues"), and its booking history is kept.</p>
          <div class="actions">
            <button type="button" class="btn btn-ghost small" @click="confirmingRetire = false">Cancel</button>
            <button type="button" class="btn btn-solid small danger" @click="proceedWithRetire">
              Yes, retire
            </button>
          </div>
        </div>

        <div v-if="retireWarning" class="retire-warning">
          <p>{{ retireWarning }}</p>
          <div class="actions">
            <button type="button" class="btn btn-ghost small" @click="retireWarning = ''">Cancel</button>
            <button type="button" class="btn btn-solid small danger" @click="confirmRetire">
              Retire anyway
            </button>
          </div>
        </div>

        <VenueActivityLog v-if="showLog" :venue-id="selected.venueId" @close="showLog = false" />
      </div>
      <div class="venue-detail empty" v-else-if="venues.length">Select a venue to view its details.</div>
      <div class="venue-detail empty" v-else>No venues are currently available.</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getVenue, getVenues, retireVenue } from '../../api/venueService.js'
import { session } from '../../store/session.js'
import VenueForm from './VenueForm.vue'
import VenueActivityLog from './VenueActivityLog.vue'

const venues = ref([])
const selected = ref(null)
const loading = ref(true)
const error = ref('')
const mode = ref('view') // 'view' | 'create' | 'edit'
const showLog = ref(false)
const showRetired = ref(false)
const confirmingRetire = ref(false)
const retireWarning = ref('')

const canWrite = computed(() => session.role === 'venue')

// Every one of selectVenue()'s network calls, plus the auto-pick of the
// first venue on mount, run asynchronously and can resolve in any order.
// Two things must both hold, or a slow/late response can silently apply
// against the wrong venue (this actually happened during testing: a stale
// auto-select resolved after a "Retire" click and retired the wrong venue):
//   1. A selectVenue() call must ignore its own result if a newer one has
//      since been started (guarded by actionToken).
//   2. The initial auto-select on mount must never fire at all once the
//      user has taken any explicit action, even if that action started
//      after refreshList() was already in flight, and even if the
//      auto-select's own selectVenue() call hasn't started yet by then
//      (guarded by userHasActed).
let actionToken = 0
let userHasActed = false

async function selectVenue(venueId) {
  userHasActed = true
  const token = ++actionToken
  try {
    error.value = ''
    const { data } = await getVenue(venueId)
    if (token !== actionToken) return
    selected.value = data
    mode.value = 'view'
    showLog.value = false
    confirmingRetire.value = false
    retireWarning.value = ''
  } catch {
    if (token === actionToken) error.value = 'Unable to load this venue’s details. Please try again.'
  }
}

async function refreshList() {
  const { data } = await getVenues(showRetired.value)
  venues.value = data
}

async function onToggleRetired() {
  await refreshList()
}

function startCreate() {
  userHasActed = true
  actionToken++
  mode.value = 'create'
  confirmingRetire.value = false
  retireWarning.value = ''
}

function startEdit() {
  userHasActed = true
  actionToken++
  mode.value = 'edit'
  confirmingRetire.value = false
  retireWarning.value = ''
}

async function onCreated(venue) {
  await refreshList()
  mode.value = 'view'
  await selectVenue(venue.venueId)
}

async function onEdited(venue) {
  await refreshList()
  actionToken++
  mode.value = 'view'
  selected.value = venue
}

// Retiring is a two-step confirmation: a plain "are you sure" first, and
// only if that's confirmed does the actual API call happen, which may then
// surface AC5's own warning (a confirmed future booking) as a second,
// more specific confirmation before it truly takes effect.
function startRetire() {
  userHasActed = true
  retireWarning.value = ''
  confirmingRetire.value = true
}

function proceedWithRetire() {
  confirmingRetire.value = false
  doRetire(false)
}

function confirmRetire() {
  doRetire(true)
}

async function doRetire(confirm) {
  try {
    await retireVenue(selected.value.venueId, confirm)
    retireWarning.value = ''
    await refreshList()
    selected.value = null
  } catch (err) {
    if (err.response?.status === 409) {
      retireWarning.value = err.response.data?.detail || 'This venue has bookings that would be affected.'
    } else {
      error.value = 'Unable to retire this venue. Please try again.'
    }
  }
}

onMounted(async () => {
  try {
    await refreshList()
    // userHasActed may already be true here if the user clicked Add/Edit/a
    // venue row while refreshList() was still in flight. In that case the
    // user's own action owns the view now, so the auto-pick must not run.
    if (venues.value.length && !userHasActed) await selectVenue(venues.value[0].venueId)
  } catch {
    error.value = 'Unable to load venues. Please try again.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.catalogue { display: grid; grid-template-columns: 270px 1fr; gap: 20px; align-items: start; }

.venue-list { display: flex; flex-direction: column; gap: 8px; }
.venue-row {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 12px;
  padding: 14px 16px;
  cursor: pointer;
  transition: background .4s var(--ease-out), border-color .4s var(--ease-out),
              transform .4s var(--ease-out);
}
.venue-row:hover { background: var(--glass-strong); transform: translateX(3px); }
.venue-row.active {
  border-color: rgba(167, 139, 250, .55);
  background: linear-gradient(90deg, rgba(124, 77, 255, .22), rgba(124, 77, 255, .04));
  box-shadow: 0 0 26px rgba(124, 77, 255, .22);
}
.venue-name {
  font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 14px;
  display: flex; align-items: center; gap: 8px;
}
.venue-meta { font-size: 12px; margin-top: 3px; color: var(--muted); }
.venue-row.retired { opacity: .55; }

.show-retired {
  display: flex; align-items: center; gap: 7px;
  font-size: 12px; color: var(--muted);
  padding: 2px 4px 6px;
  cursor: pointer;
}
.show-retired input { accent-color: var(--iris); cursor: pointer; }

.retired-tag {
  font-size: 10px; letter-spacing: .05em; text-transform: uppercase; font-weight: 600;
  color: #FF8A76; background: rgba(255, 138, 118, .15);
  padding: 2px 7px; border-radius: 999px;
}

.venue-detail {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 16px;
  padding: 26px;
}
.venue-detail.empty { display: flex; align-items: center; justify-content: center; color: var(--muted); }
.venue-detail.error { color: #FF8A76; }
.venue-detail h3 {
  margin: 0; font-size: 19px; font-weight: 500;
  display: flex; align-items: center; gap: 10px;
}
dl { margin: 0; display: grid; grid-template-columns: 150px 1fr; row-gap: 12px; }
dt { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); align-self: center; }
dd { margin: 0; font-size: 14px; line-height: 1.6; color: var(--body); }

.add-btn { width: 100%; margin-bottom: 4px; }

.detail-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; gap: 12px; }
.detail-actions { display: flex; gap: 8px; flex-shrink: 0; }
.btn.small { padding: 6px 14px; font-size: 12px; }
.btn.danger { color: #FF8A76; }
.btn-solid.danger { background: linear-gradient(135deg, #FF8A76, #E5533D); }

.retire-warning {
  margin-top: 20px;
  padding: 16px;
  border-radius: 12px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .3);
}
.retire-warning p { margin: 0 0 12px; font-size: 13px; color: var(--text); line-height: 1.6; }
.retire-warning .actions { display: flex; justify-content: flex-end; gap: 10px; }

@media (max-width: 720px) {
  .catalogue { grid-template-columns: 1fr; }
}
</style>
