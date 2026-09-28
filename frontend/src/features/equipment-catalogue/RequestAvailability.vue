<template>
  <div class="request-check">
    <p v-if="loading" class="empty">Loading equipment requests…</p>
    <p v-else-if="error" class="empty error">{{ error }}</p>
    <p v-else-if="!groups.length" class="empty">No open equipment requests to check.</p>
    <article v-for="group in groups" :key="group.eventId" class="event-card">
      <div class="event-header">
        <h3>Event {{ group.eventId }}</h3>
        <button type="button" class="btn btn-ghost small" @click="check(group.eventId)">Check availability</button>
      </div>
      <p class="asked">
        Asked for
        <span v-for="request in group.requests" :key="request.requestId">
          {{ request.quantity }} × {{ request.equipmentId }}
        </span>
      </p>
      <p v-if="results[group.eventId]" class="verdict" :class="{ short: !results[group.eventId].canMeet }">
        {{ results[group.eventId].canMeet ? 'This request can be met.' : 'This request cannot be met.' }}
        Checking does not reserve anything.
      </p>
      <table v-if="results[group.eventId]" class="lines">
        <thead>
          <tr>
            <th>Equipment</th>
            <th>Requested</th>
            <th>Available</th>
            <th>Shortfall</th>
            <th>Held by</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(line, index) in results[group.eventId].lines" :key="`${line.equipmentId}-${index}`">
            <td>{{ line.name }}</td>
            <td>{{ line.requestedQuantity }}</td>
            <td>{{ line.availableQuantity }}</td>
            <td>{{ line.shortfall }}</td>
            <td>{{ heldBy(line) }}</td>
          </tr>
        </tbody>
      </table>
    </article>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { checkEquipmentAvailability, getEquipmentRequests } from '../../api/equipmentService.js'

const requests = ref([])
const results = ref({})
const loading = ref(true)
const error = ref('')

const groups = computed(() => {
  const grouped = new Map()
  for (const request of requests.value) {
    if (request.status === 'rejected' || request.status === 'cancelled') continue
    if (!grouped.has(request.eventId)) grouped.set(request.eventId, [])
    grouped.get(request.eventId).push(request)
  }
  return [...grouped.entries()].map(([eventId, rows]) => ({ eventId, requests: rows }))
})

function heldBy(line) {
  const conflicts = line.conflictingEvents || []
  if (!conflicts.length) return '—'
  return conflicts.map((item) => `${item.eventId} (${item.quantity})`).join(', ')
}

async function check(eventId) {
  error.value = ''
  try {
    const { data } = await checkEquipmentAvailability({ eventId })
    results.value = { ...results.value, [eventId]: data }
  } catch {
    error.value = 'Unable to check that request. Please try again.'
  }
}

onMounted(async () => {
  try {
    const { data } = await getEquipmentRequests()
    requests.value = data
  } catch {
    error.value = 'Unable to load equipment requests. Please try again.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.request-check { display: flex; flex-direction: column; gap: 14px; }
.event-card {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 16px;
  padding: 18px 20px;
}
.event-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
h3 { margin: 0; font-size: 16px; font-weight: 500; }
.asked { margin: 10px 0 0; color: var(--muted); font-size: 13px; display: flex; flex-wrap: wrap; gap: 8px 14px; }
.verdict { margin: 12px 0 0; font-size: 14px; }
.verdict.short { color: #ffb4a8; }
.lines { width: 100%; margin-top: 12px; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 8px 10px 8px 0; border-bottom: 1px solid var(--hairline); }
.empty { margin: 0; color: var(--muted); }
.error { color: #ffb4a8; }
</style>
