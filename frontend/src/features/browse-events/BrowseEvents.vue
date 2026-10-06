<template>
  <div class="browse">
    <div class="filters">
      <input v-model="search" type="search" placeholder="Search events" data-testid="browse-search" />
      <select v-model="category" data-testid="browse-filter-category">
        <option value="">All categories</option>
        <option v-for="name in categories" :key="name" :value="name">{{ name }}</option>
      </select>
      <input v-model="fromDate" type="date" data-testid="browse-filter-from" />
    </div>

    <p v-if="loading" class="empty-note">Loading events…</p>
    <p v-else-if="error" class="form-error" data-testid="browse-error">{{ error }}</p>
    <p v-else-if="!visible.length" class="empty-note" data-testid="browse-empty">No events are open for registration.</p>

    <article
      v-for="event in visible"
      :key="event.eventId"
      class="event-card"
      :data-testid="`browse-event-${event.eventId}`"
      :data-full="event.full ? 'true' : 'false'"
    >
      <div class="event-name">{{ event.eventName }}</div>
      <div class="event-meta">
        <span data-testid="browse-category">{{ event.category }}</span>
        · <span data-testid="browse-date">{{ datePart(event.proposedStartAt) }}</span>
        · <span data-testid="browse-start">{{ timePart(event.proposedStartAt) }}</span>
        – <span data-testid="browse-end">{{ timePart(event.proposedEndAt) }}</span>
      </div>
      <p>{{ event.venueName }} · {{ event.venueLocation }}</p>
      <p data-testid="browse-remaining">
        {{ event.full ? 'Full' : `${event.remaining} places remaining` }}
      </p>
      <div class="actions">
        <button type="button" class="btn btn-outline" @click="open(event.eventId)">View</button>
        <button
          v-if="!event.full"
          type="button"
          class="btn btn-solid"
          data-testid="event-register"
          @click="open(event.eventId)"
        >
          Register
        </button>
      </div>
    </article>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getOpenEvents } from '../../api/eventService.js'

const router = useRouter()
const events = ref([])
const loading = ref(true)
const error = ref('')
const search = ref('')
const category = ref('')
const fromDate = ref('')

const categories = computed(() => [...new Set(events.value.map((event) => event.category).filter(Boolean))])

const visible = computed(() => events.value.filter((event) => {
  if (search.value && !event.eventName.toLowerCase().includes(search.value.toLowerCase())) return false
  if (category.value && event.category !== category.value) return false
  if (fromDate.value && event.proposedStartAt && event.proposedStartAt.slice(0, 10) < fromDate.value) return false
  return true
}))

function datePart(value) {
  return value ? new Date(value).toLocaleDateString() : ''
}

function timePart(value) {
  return value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
}

function open(eventId) {
  router.push(`/app/browse/${eventId}`)
}

onMounted(async () => {
  try {
    const { data } = await getOpenEvents()
    events.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load events.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.browse, .filters { display: flex; flex-direction: column; gap: 12px; max-width: 720px; }
.filters { flex-direction: row; flex-wrap: wrap; }
.event-card {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 16px 18px;
}
.event-name { font-size: 16px; }
.event-meta, .empty-note { font-size: 13px; color: var(--muted); }
.actions { display: flex; gap: 8px; margin-top: 10px; }
</style>
