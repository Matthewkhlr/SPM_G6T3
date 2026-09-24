<template>
  <div class="drafts">
    <p v-if="loading" class="empty-note">Loading your drafts…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="!drafts.length" class="empty-note">No drafts saved yet.</p>

    <div v-for="draft in drafts" :key="draft.eventId" class="draft-card">
      <div class="draft-head">
        <div>
          <div class="draft-name">
            {{ draft.eventName || 'Untitled event' }}
            <span class="draft-pill">Draft</span>
          </div>
          <div class="draft-meta">{{ formatRange(draft.proposedStartAt, draft.proposedEndAt) }}</div>
        </div>
        <button class="btn btn-outline" @click="edit(draft.eventId)">Edit</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getMyDrafts } from '../../api/eventService.js'
import { editDraft } from '../../store/draftEditor.js'

const emit = defineEmits(['edit-draft'])

const drafts = ref([])
const loading = ref(true)
const error = ref('')

function formatRange(start, end) {
  if (!start && !end) return 'No date set yet'
  if (!start || !end) return 'Date incomplete'
  return `${new Date(start).toLocaleString()} – ${new Date(end).toLocaleString()}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getMyDrafts()
    drafts.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load your drafts. Please try again.'
  } finally {
    loading.value = false
  }
}

function edit(eventId) {
  editDraft(eventId)
  emit('edit-draft')
}

onMounted(load)
</script>

<style scoped>
.drafts { display: flex; flex-direction: column; gap: 12px; max-width: 720px; }

.empty-note { font-size: 14px; color: var(--muted); }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
}

.draft-card {
  background: var(--glass);
  border: 1px dashed var(--hairline);
  border-radius: 14px;
  padding: 18px 20px;
  transition: border-color .4s var(--ease-out), background .4s var(--ease-out);
}
.draft-card:hover { border-color: rgba(167, 139, 250, .3); background: var(--glass-strong); }
.draft-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.draft-name {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 500;
  color: var(--text);
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.draft-meta { font-size: 12px; margin-top: 4px; color: var(--muted); }

/* Deliberately distinct from the solid purple .status-pill used for
   submitted requests elsewhere — dashed and muted, to read as "not sent yet". */
.draft-pill {
  display: inline-block;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
  background: transparent;
  border: 1px dashed var(--hairline);
  border-radius: 999px;
  padding: 3px 10px;
}

@media (max-width: 560px) {
  .draft-head { flex-direction: column; align-items: flex-start; }
}
</style>
