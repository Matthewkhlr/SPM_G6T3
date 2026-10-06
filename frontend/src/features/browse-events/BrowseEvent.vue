<template>
  <div class="browse-detail">
    <button type="button" class="btn btn-ghost" @click="router.push('/app')">← Browse events</button>
    <p v-if="loading" class="empty-note">Loading event…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <template v-else-if="event">
      <h1>{{ event.eventName }}</h1>
      <p data-testid="browse-description">{{ event.description }}</p>
      <p data-testid="browse-accessibility">{{ event.accessibilityNeeds }}</p>
      <p data-testid="browse-closes-at">Registration closes {{ event.registrationClosesAt }}</p>
      <p data-testid="browse-remaining">{{ event.remaining }} places remaining</p>
      <p>{{ event.venueName }} · {{ event.venueLocation }}</p>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getOpenEvent } from '../../api/eventService.js'

const route = useRoute()
const router = useRouter()
const event = ref(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const { data } = await getOpenEvent(route.params.id)
    event.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'This event is not open.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.browse-detail { display: flex; flex-direction: column; gap: 12px; max-width: 720px; }
.empty-note { color: var(--muted); }
</style>
