<template>
  <!-- SPM-72: the assigned coordinator confirms the event once its venue and
       equipment are in place and the Safety Officer has approved it (SPM-120). -->
  <section v-if="visible" class="panel confirmation" data-testid="event-confirmation">
    <div class="panel-head">
      <h2>Confirm the event</h2>
      <button
        v-if="status?.ready"
        type="button"
        class="btn btn-solid small"
        :disabled="confirming"
        data-testid="event-confirm"
        @click="confirm"
      >
        {{ confirming ? 'Confirming…' : 'Confirm event' }}
      </button>
    </div>

    <p v-if="loading" class="empty-note">Checking the arrangements…</p>
    <p v-else-if="loadError" class="form-error">{{ loadError }}</p>

    <p v-else-if="status?.ready" class="ready" data-testid="confirm-ready">
      The venue and equipment are in place and the Safety Officer approved the plan. Confirming tells the organiser,
      venue staff, and technical support, and opens registration to attendees when its period starts.
    </p>

    <!-- AC2: unavailable while anything is outstanding, naming what is missing. -->
    <div v-else-if="status" class="missing" data-testid="confirm-missing">
      <p>The event can be confirmed once these are done:</p>
      <ul>
        <li v-for="(gap, index) in status.missing" :key="index" :class="gap.kind">
          <span class="kind">{{ KIND_LABELS[gap.kind] }}</span>
          <span>{{ gap.message }}</span>
          <template v-if="gap.equipmentId && canChangeEquipment">
            <button
              v-if="markingId !== gap.equipmentId"
              type="button"
              class="btn btn-ghost small"
              :data-testid="`equipment-not-required-${gap.equipmentId}`"
              @click="startMarking(gap.equipmentId)"
            >
              Mark not required
            </button>
            <form v-else class="reason-form" @submit.prevent="markNotRequired(gap.equipmentId)">
              <input
                v-model="reason"
                type="text"
                maxlength="2000"
                placeholder="Why is it no longer needed?"
                :data-testid="`equipment-not-required-reason-${gap.equipmentId}`"
              />
              <button type="button" class="btn btn-ghost small" @click="markingId = ''">Cancel</button>
              <button type="submit" class="btn btn-solid small" :disabled="busy || !reason.trim()" data-testid="equipment-not-required-save">
                Save
              </button>
            </form>
          </template>
        </li>
      </ul>
    </div>

    <!-- AC1: equipment explicitly recorded as not required, with the reason. -->
    <ul v-if="notRequiredLines.length" class="not-required">
      <li v-for="line in notRequiredLines" :key="line.equipmentId" :data-testid="`equipment-not-required-line-${line.equipmentId}`">
        {{ line.quantity }} × {{ line.equipmentId }} recorded as not required: {{ line.notRequiredReason }}
        <button
          v-if="canChangeEquipment"
          type="button"
          class="btn btn-ghost small"
          :disabled="busy"
          @click="markRequired(line.equipmentId)"
        >
          Needed again
        </button>
      </li>
    </ul>

    <p v-if="actionError" class="form-error">{{ actionError }}</p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import {
  confirmEvent,
  getConfirmation,
  markEquipmentNotRequired,
  markEquipmentRequired,
} from '../../api/eventService.js'
import { CONFIRMATION_PATH_STATUSES, SAFETY_SUBMITTABLE_STATUSES } from '../../config/eventStatus.js'
import { session } from '../../store/session.js'

const props = defineProps({ event: { type: Object, required: true } })
// Confirming or changing equipment needs changes the event, so the page re-reads it.
const emit = defineEmits(['changed'])

const KIND_LABELS = { venue: 'Venue', equipment: 'Equipment', safety: 'Safety review', status: 'Stage' }

const status = ref(null)
const loading = ref(false)
const loadError = ref('')
const confirming = ref(false)
const busy = ref(false)
const actionError = ref('')
const markingId = ref('')
const reason = ref('')

const isAssignedCoordinator = computed(
  () => session.role === 'coordinator' && !!props.event.coordinatorId && props.event.coordinatorId === session.userId,
)
const visible = computed(() => isAssignedCoordinator.value && CONFIRMATION_PATH_STATUSES.includes(props.event.status))
// Equipment needs change only in planning, before the safety review.
const canChangeEquipment = computed(() => SAFETY_SUBMITTABLE_STATUSES.includes(props.event.status))
const notRequiredLines = computed(() => (props.event.equipmentLines || []).filter((line) => line.notRequired))

function errorText(err, fallback) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(' ')
  return detail?.message || fallback
}

async function load() {
  if (!visible.value) return
  loading.value = true
  loadError.value = ''
  try {
    const { data } = await getConfirmation(props.event.eventId)
    status.value = data
  } catch (err) {
    loadError.value = errorText(err, 'Could not check the arrangements. Please try again.')
  } finally {
    loading.value = false
  }
}

async function confirm() {
  confirming.value = true
  actionError.value = ''
  try {
    await confirmEvent(props.event.eventId)
    emit('changed', 'confirmed')
  } catch (err) {
    const detail = err.response?.data?.detail
    if (err.response?.status === 409 && detail?.gaps) {
      status.value = { ready: false, missing: detail.gaps }
    } else {
      actionError.value = errorText(err, 'Could not confirm the event. Please try again.')
    }
  } finally {
    confirming.value = false
  }
}

function startMarking(equipmentId) {
  markingId.value = equipmentId
  reason.value = ''
}

async function markNotRequired(equipmentId) {
  busy.value = true
  actionError.value = ''
  try {
    await markEquipmentNotRequired(props.event.eventId, equipmentId, reason.value)
    markingId.value = ''
    emit('changed')
  } catch (err) {
    actionError.value = errorText(err, 'Could not record that. Please try again.')
  } finally {
    busy.value = false
  }
}

async function markRequired(equipmentId) {
  busy.value = true
  actionError.value = ''
  try {
    await markEquipmentRequired(props.event.eventId, equipmentId)
    emit('changed')
  } catch (err) {
    actionError.value = errorText(err, 'Could not record that. Please try again.')
  } finally {
    busy.value = false
  }
}

// The page re-reads the event after any change; check again when it does.
watch(() => [props.event.status, JSON.stringify(props.event.equipmentLines || [])], load)
onMounted(load)
</script>

<style scoped>
.panel {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 22px 24px;
  margin-top: 18px;
}
.panel-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
.panel h2 { margin: 0; font-size: 16px; font-weight: 500; }
.empty-note { font-size: 14px; color: var(--muted); margin: 0; }
.btn.small { padding: 7px 14px; font-size: 13px; }
.btn:disabled { opacity: .55; cursor: not-allowed; }

.ready, .missing {
  font-size: 13px;
  line-height: 1.6;
  border-radius: 9px;
  padding: 12px 14px;
  margin: 0;
}
.ready { color: var(--halo); background: rgba(124, 77, 255, .1); border: 1px solid rgba(167, 139, 250, .25); }
.missing { color: var(--body); border: 1px solid rgba(255, 196, 120, .3); background: rgba(255, 170, 80, .06); }
.missing p { margin: 0 0 8px; color: #FFD9A8; }
.missing ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.missing li { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: baseline; }
.kind {
  font-size: 10px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
  border: 1px solid var(--hairline);
  border-radius: 999px;
  padding: 1px 8px;
}
.reason-form { display: flex; gap: 6px; flex-wrap: wrap; width: 100%; }
.reason-form input {
  flex: 1;
  min-width: 200px;
  box-sizing: border-box;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  padding: 7px 10px;
  font-size: 13px;
  color: var(--text);
  font-family: 'Inter', sans-serif;
}
.not-required { list-style: none; margin: 12px 0 0; padding: 0; font-size: 13px; color: var(--muted); display: flex; flex-direction: column; gap: 6px; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 12px 0 0;
}
</style>
