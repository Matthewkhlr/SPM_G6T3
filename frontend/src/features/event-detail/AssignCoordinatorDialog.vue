<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" data-testid="assign-dialog">
      <h3>{{ event.coordinatorId ? 'Change coordinator' : 'Choose a coordinator' }}</h3>
      <p class="sub">{{ event.eventName }}</p>

      <p v-if="loading" class="empty-note">Loading coordinators…</p>
      <p v-else-if="loadError" class="form-error">{{ loadError }}</p>
      <div v-else class="candidates" role="radiogroup" aria-label="Coordinator">
        <button
          v-for="candidate in candidates"
          :key="candidate.userId"
          type="button"
          role="radio"
          class="candidate"
          :class="{ selected: chosen === candidate.userId }"
          :aria-checked="chosen === candidate.userId"
          :data-testid="`assign-candidate-${candidate.userId}`"
          @click="chosen = candidate.userId"
        >
          <span class="who">
            <span class="name">
              {{ candidate.name }}
              <span v-if="candidate.userId === session.userId" class="tag">You</span>
              <span v-if="candidate.userId === event.coordinatorId" class="tag">Current</span>
            </span>
            <span class="email">{{ candidate.email }}</span>
          </span>
          <!-- SPM-66 AC2/AC3: shown for information only — there is no workload limit. -->
          <span class="count">{{ candidate.activeEventCount }} active {{ candidate.activeEventCount === 1 ? 'event' : 'events' }}</span>
        </button>
      </div>

      <p v-if="error" class="form-error">{{ error }}</p>
      <div class="modal-actions">
        <button type="button" class="btn btn-outline" @click="emit('close')">Cancel</button>
        <button
          type="button"
          class="btn btn-solid"
          :disabled="!chosen || saving || loading"
          data-testid="assign-confirm"
          @click="confirm"
        >
          {{ saving ? 'Assigning…' : 'Assign' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { assignCoordinator, getCoordinatorCandidates } from '../../api/eventService.js'
import { session } from '../../store/session.js'

const props = defineProps({ event: { type: Object, required: true } })
const emit = defineEmits(['close', 'assigned'])

const candidates = ref([])
const chosen = ref(props.event.coordinatorId || '')
const loading = ref(true)
const loadError = ref('')
const saving = ref(false)
const error = ref('')

async function load() {
  try {
    const { data } = await getCoordinatorCandidates()
    candidates.value = data
  } catch (err) {
    loadError.value = err.response?.data?.detail || 'Could not load the coordinators. Please try again.'
  } finally {
    loading.value = false
  }
}

async function confirm() {
  saving.value = true
  error.value = ''
  try {
    const { data } = await assignCoordinator(props.event.eventId, chosen.value)
    emit('assigned', data)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not assign the coordinator. Please try again.'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(5, 2, 14, .7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center; z-index: 20;
  padding: 16px;
}
.modal {
  background: linear-gradient(160deg, #1A0C3B, #0D0524);
  border: 1px solid rgba(167, 139, 250, .28);
  box-shadow: 0 30px 90px rgba(4, 1, 12, .7), 0 0 60px rgba(124, 77, 255, .18);
  border-radius: 18px;
  padding: 30px;
  width: 440px;
  max-width: 100%;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
}
.modal h3 { margin: 0 0 4px; font-size: 18px; font-weight: 500; }
.sub { margin: 0 0 18px; font-size: 13px; color: var(--muted); }
.empty-note { font-size: 14px; color: var(--muted); }

.candidates { display: flex; flex-direction: column; gap: 8px; }
.candidate {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  width: 100%;
  text-align: left;
  background: rgba(255, 255, 255, .03);
  border: 1px solid var(--hairline);
  border-radius: 10px;
  padding: 11px 14px;
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
.candidate:hover { border-color: rgba(167, 139, 250, .4); }
.candidate.selected {
  border-color: rgba(167, 139, 250, .75);
  background: rgba(124, 77, 255, .14);
  box-shadow: 0 0 0 3px rgba(124, 77, 255, .14);
}
.who { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.name { font-size: 14px; }
.email { font-size: 12px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; }
.count { font-size: 12px; color: var(--body); white-space: nowrap; }
.tag {
  font-size: 10px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--halo);
  background: rgba(124, 77, 255, .18);
  border-radius: 999px;
  padding: 1px 7px;
  margin-left: 6px;
}

.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 14px 0 0;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.btn:disabled { opacity: .55; cursor: not-allowed; }
</style>
