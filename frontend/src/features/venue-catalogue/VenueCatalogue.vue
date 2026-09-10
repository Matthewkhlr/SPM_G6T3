<template>
  <div class="catalogue">
    <div class="venue-list">
      <div
        v-for="venue in venues"
        :key="venue.venueId"
        class="venue-row"
        :class="{ active: selected?.venueId === venue.venueId }"
        @click="selectVenue(venue.venueId)"
      >
        <div class="venue-name">{{ venue.name }}</div>
        <div class="venue-meta">{{ venue.location }} · Capacity {{ venue.capacity }}</div>
      </div>
    </div>

    <div v-if="loading" class="venue-detail empty">Loading venues…</div>
    <div v-else-if="error" class="venue-detail empty error">{{ error }}</div>
    <div class="venue-detail" v-else-if="selected">
      <h3>{{ selected.name }}</h3>
      <dl>
        <dt>Location</dt><dd>{{ selected.location }}</dd>
        <dt>Capacity</dt><dd>{{ selected.capacity }} people</dd>
        <dt>Facilities</dt><dd>{{ selected.facilities.join(', ') }}</dd>
        <dt>Accessibility</dt><dd>{{ selected.accessibility }}</dd>
        <dt>Supported layouts</dt><dd>{{ selected.layouts.join(', ') }}</dd>
        <dt>Operating hours</dt><dd>{{ selected.operatingHours }}</dd>
        <dt>Turnaround needed</dt><dd>{{ selected.turnaroundMinutes }} minutes between bookings</dd>
      </dl>
    </div>
    <div class="venue-detail empty" v-else-if="venues.length">Select a venue to view its details.</div>
    <div class="venue-detail empty" v-else>No venues are currently available.</div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getVenue, getVenues } from '../../api/venueService.js'

const venues = ref([])
const selected = ref(null)
const loading = ref(true)
const error = ref('')

async function selectVenue(venueId) {
  try {
    error.value = ''
    const { data } = await getVenue(venueId)
    selected.value = data
  } catch {
    error.value = 'Unable to load this venue’s details. Please try again.'
  }
}

onMounted(async () => {
  try {
    const { data } = await getVenues()
    venues.value = data
    if (data.length) await selectVenue(data[0].venueId)
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
.venue-name { font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 14px; }
.venue-meta { font-size: 12px; margin-top: 3px; color: var(--muted); }

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
.venue-detail h3 { margin: 0 0 20px; font-size: 19px; font-weight: 500; }
dl { margin: 0; display: grid; grid-template-columns: 150px 1fr; row-gap: 12px; }
dt { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); align-self: center; }
dd { margin: 0; font-size: 14px; line-height: 1.6; color: var(--body); }

@media (max-width: 720px) {
  .catalogue { grid-template-columns: 1fr; }
}
</style>
