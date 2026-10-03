<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" data-testid="approve-dialog">
      <h3>Approve this request?</h3>
      <p class="sub">{{ event.eventName }}</p>

      <p class="body">
        The event moves to Planning and the organiser is told that ConnectSphere has taken it on.
        Approving does not book a venue or reserve equipment; those stay outstanding until you arrange them.
      </p>

      <!-- SPM-69 AC4: the customer allows approving with clarifications open, but only knowingly. -->
      <p v-if="needsConfirm" class="warning" data-testid="approve-open-clarifications-warning">
        This request still has open clarifications with the organiser. Approving now moves it to
        Planning without waiting for their answers.
      </p>

      <label for="approve-note">Note to the organiser (optional)</label>
      <textarea
        id="approve-note"
        v-model="note"
        rows="3"
        maxlength="2000"
        placeholder="Anything the organiser should know"
        data-testid="approve-note"
      ></textarea>

      <p v-if="error" class="form-error">{{ error }}</p>
      <div class="modal-actions">
        <button type="button" class="btn btn-outline" @click="emit('close')">Cancel</button>
        <button
          v-if="needsConfirm"
          type="button"
          class="btn btn-solid"
          :disabled="saving"
          data-testid="approve-confirm-anyway"
          @click="submit"
        >
          {{ saving ? 'Approving…' : 'Approve anyway' }}
        </button>
        <button
          v-else
          type="button"
          class="btn btn-solid"
          :disabled="saving"
          data-testid="approve-submit"
          @click="submit"
        >
          {{ saving ? 'Approving…' : 'Approve' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { approveEvent } from '../../api/eventService.js'

const props = defineProps({ event: { type: Object, required: true } })
const emit = defineEmits(['close', 'approved'])

const note = ref('')
const saving = ref(false)
const error = ref('')
// Set when the server reports clarifications this page did not know about yet.
const serverWarned = ref(false)
const needsConfirm = computed(() => props.event.hasOpenClarifications || serverWarned.value)

async function submit() {
  saving.value = true
  error.value = ''
  try {
    const { data } = await approveEvent(props.event.eventId, note.value, needsConfirm.value)
    emit('approved', data)
  } catch (err) {
    const detail = err.response?.data?.detail
    if (detail?.requiresConfirmation) {
      serverWarned.value = true
    } else {
      error.value = (typeof detail === 'string' && detail) || 'Could not approve this request. Please try again.'
    }
  } finally {
    saving.value = false
  }
}
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
.sub { margin: 0 0 14px; font-size: 13px; color: var(--muted); }
.body { margin: 0 0 14px; font-size: 14px; line-height: 1.6; color: var(--body); }

.warning {
  font-size: 13px;
  line-height: 1.6;
  color: #FFD9A8;
  background: rgba(255, 170, 80, .08);
  border: 1px solid rgba(255, 196, 120, .3);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 0 0 14px;
}

label {
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); display: block; margin-bottom: 6px;
}
textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  padding: 11px 12px;
  font-size: 14px;
  color: var(--text);
  font-family: 'Inter', sans-serif;
  resize: vertical;
  line-height: 1.6;
}
textarea:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .6);
  box-shadow: 0 0 0 3px rgba(124, 77, 255, .16);
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
