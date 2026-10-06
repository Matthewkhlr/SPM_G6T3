<template>
  <div class="readiness">
    <button type="button" class="btn btn-ghost" @click="router.push(`/app/events/${route.params.id}`)">← Event</button>
    <p v-if="loading" class="empty-note">Loading readiness…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <article v-for="row in rows" :key="row.itemId" class="event-card" data-testid="readiness-row">
      <p data-testid="readiness-category">{{ row.category }}</p>
      <p data-testid="readiness-handler">{{ row.handlerName || row.personnel }}</p>
      <p data-testid="readiness-handler-contact">{{ row.handlerEmail || row.handlerPhone }}</p>
      <p data-testid="readiness-status">{{ row.status }}</p>
      <p data-testid="readiness-assigned-at">{{ row.assignedAt }}</p>
      <div data-testid="readiness-attachments">
        <a
          v-for="file in row.attachments"
          :key="file.url"
          data-testid="readiness-attachment-link"
          :href="file.url"
        >{{ file.name || file.url }}</a>
        <span v-if="!row.attachments.length">No attachments</span>
      </div>
      <button type="button" data-testid="readiness-confirm-status" @click="pending = row">Confirm status</button>
    </article>

    <div v-if="pending" class="modal" data-testid="readiness-confirm-dialog" role="dialog">
      <p>Confirm this {{ pending.category }} line as settled?</p>
      <button type="button" @click="confirm">Confirm</button>
      <button type="button" @click="pending = null">Cancel</button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getReadiness, updateReadinessItem } from '../../api/eventService.js'

const route = useRoute()
const router = useRouter()
const rows = ref([])
const loading = ref(true)
const error = ref('')
const pending = ref(null)

async function load() {
  loading.value = true
  try {
    const { data } = await getReadiness(route.params.id)
    rows.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load readiness.'
  } finally {
    loading.value = false
  }
}

async function confirm() {
  const row = pending.value
  pending.value = null
  await updateReadinessItem(route.params.id, row.itemId, { status: 'confirmed' })
  await load()
}

onMounted(load)
</script>

<style scoped>
.readiness { display: flex; flex-direction: column; gap: 12px; max-width: 720px; }
.event-card { border: 1px solid var(--hairline); border-radius: 14px; padding: 16px; }
.modal { border: 1px solid var(--hairline); border-radius: 14px; padding: 16px; }
</style>
