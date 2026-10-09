<template>
  <!-- SPM-120, change 6: Venue Staff send the confirmed venue arrangements and
       technical support the technical ones; the review opens once both are in. -->
  <section v-if="visible && loaded" class="panel handoff" data-testid="safety-handoff">
    <h2>Sending to the Safety Officer</h2>
    <p class="hint">
      Venue Staff send the venue arrangements and technical support send the technical arrangements once they are
      confirmed. The safety review starts as soon as everything the event needs is in.
    </p>
    <p v-if="loadError" class="form-error">{{ loadError }}</p>

    <ul v-if="handoff" class="parts">
      <li data-testid="safety-handoff-venue-status">
        <span class="kind">Venue arrangements</span>
        <span v-if="handoff.venue">Sent by {{ nameOf(handoff.venue.sentBy, 'Venue Staff') }} on {{ formatUtc(handoff.venue.sentAt) }}</span>
        <span v-else class="waiting">Waiting for Venue Staff</span>
      </li>
      <li data-testid="safety-handoff-technical-status">
        <span class="kind">Technical arrangements</span>
        <span v-if="!handoff.technicalNeeded" class="muted">Not needed: the event has no equipment</span>
        <span v-else-if="handoff.technical">
          Sent by {{ nameOf(handoff.technical.sentBy, 'technical support') }} on {{ formatUtc(handoff.technical.sentAt) }}
        </span>
        <span v-else class="waiting">Waiting for technical support</span>
      </li>
    </ul>

    <form v-if="canSend" class="send-form" data-testid="safety-handoff-form" @submit.prevent="send">
      <label for="safety-handoff-note">{{ isVenueStaff ? 'Crowd movement' : 'Equipment placement' }}</label>
      <textarea
        id="safety-handoff-note"
        v-model="note"
        rows="3"
        maxlength="4000"
        :placeholder="isVenueStaff ? 'How people arrive, move through, and leave the venue' : 'Where each piece of equipment goes'"
        data-testid="safety-handoff-note"
      ></textarea>
      <div v-if="missing.length" class="warning" data-testid="safety-handoff-missing">
        <p>Not ready to send yet:</p>
        <ul>
          <li v-for="(reason, index) in missing" :key="index">{{ reason }}</li>
        </ul>
      </div>
      <p v-if="sendError" class="form-error">{{ sendError }}</p>
      <div class="form-actions">
        <button type="submit" class="btn btn-solid small" :disabled="saving || !note.trim()" data-testid="safety-handoff-send">
          {{ saving ? 'Sending…' : sendLabel }}
        </button>
      </div>
    </form>

    <p v-if="notice" class="notice" data-testid="safety-handoff-notice">{{ notice }}</p>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { getSafetyHandoff, sendTechnicalArrangements, sendVenueArrangements } from '../../api/eventService.js'
import { getUsers } from '../../api/userService.js'
import { SAFETY_SUBMITTABLE_STATUSES } from '../../config/eventStatus.js'
import { session } from '../../store/session.js'
import { formatUtc } from '../../utils/datetime.js'

const props = defineProps({ event: { type: Object, required: true } })
// The last part opens the review, which changes the event's status.
const emit = defineEmits(['changed'])

const handoff = ref(null)
const names = ref({})
const loaded = ref(false)
const loadError = ref('')
const note = ref('')
const missing = ref([])
const sendError = ref('')
const saving = ref(false)
const notice = ref('')

const isVenueStaff = computed(() => session.role === 'venue')
const isTech = computed(() => session.role === 'techsupport')
const isAssignedCoordinator = computed(
  () => session.role === 'coordinator' && !!props.event.coordinatorId && props.event.coordinatorId === session.userId,
)
const visible = computed(
  () =>
    SAFETY_SUBMITTABLE_STATUSES.includes(props.event.status) &&
    (isVenueStaff.value || isTech.value || isAssignedCoordinator.value),
)
const ownPart = computed(() => (isVenueStaff.value ? handoff.value?.venue : handoff.value?.technical) || null)
const canSend = computed(() => !!handoff.value && (isVenueStaff.value || (isTech.value && handoff.value.technicalNeeded)))
const sendLabel = computed(() => {
  const what = isVenueStaff.value ? 'venue' : 'technical'
  return ownPart.value ? `Send the ${what} arrangements again` : `Send the ${what} arrangements to the Safety Officer`
})

function nameOf(userId, fallback) {
  return names.value[userId] || fallback
}

function errorText(err, fallback) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(' ')
  return detail?.message || fallback
}

async function load() {
  loadError.value = ''
  try {
    const { data } = await getSafetyHandoff(props.event.eventId)
    handoff.value = data
    note.value = ownPart.value?.note || ''
  } catch (err) {
    loadError.value = errorText(err, 'Could not load what has been sent to the Safety Officer.')
  } finally {
    loaded.value = true
  }
}

// Names are for display only; without them the panel still works.
async function loadNames() {
  try {
    const { data } = await getUsers()
    names.value = Object.fromEntries(data.map((user) => [user.userId, user.userName]))
  } catch {
    names.value = {}
  }
}

async function send() {
  saving.value = true
  missing.value = []
  sendError.value = ''
  notice.value = ''
  try {
    const { eventId } = props.event
    const { data } = isVenueStaff.value
      ? await sendVenueArrangements(eventId, note.value)
      : await sendTechnicalArrangements(eventId, note.value)
    if (data.review) {
      emit('changed')
      return
    }
    handoff.value = data
    notice.value = isVenueStaff.value
      ? 'Sent. The safety review starts once technical support send the technical arrangements.'
      : 'Sent. The safety review starts once Venue Staff send the venue arrangements.'
  } catch (err) {
    const detail = err.response?.data?.detail
    if (err.response?.status === 409 && Array.isArray(detail?.gaps)) {
      missing.value = detail.gaps.map((gap) => gap.message)
    } else {
      sendError.value = errorText(err, 'Could not send the arrangements. Please try again.')
    }
  } finally {
    saving.value = false
  }
}

// Shown in planning only; load whenever the event comes back to planning.
watch(
  visible,
  (shown) => {
    if (!shown) return
    load()
    loadNames()
  },
  { immediate: true },
)
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
.panel h2 { margin: 0 0 8px; font-size: 16px; font-weight: 500; }
.hint { font-size: 13px; color: var(--muted); line-height: 1.55; margin: 0 0 12px; }
.btn.small { padding: 7px 14px; font-size: 13px; }
.btn:disabled { opacity: .55; cursor: not-allowed; }

.parts { list-style: none; margin: 0 0 14px; padding: 0; display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: var(--body); }
.parts li { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: baseline; }
.kind { min-width: 170px; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.waiting { color: #FFD9A8; }
.muted { color: var(--muted); }

.send-form { border: 1px solid var(--hairline); border-radius: 12px; padding: 16px; margin: 0 0 14px; }
label { display: block; margin-bottom: 6px; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  padding: 10px 12px;
  margin-bottom: 12px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--text);
  font-family: 'Inter', sans-serif;
  resize: vertical;
}
textarea:focus { outline: none; border-color: rgba(167, 139, 250, .6); box-shadow: 0 0 0 3px rgba(124, 77, 255, .16); }
.form-actions { display: flex; justify-content: flex-end; gap: 8px; }

.notice, .warning {
  font-size: 13px;
  line-height: 1.6;
  border-radius: 9px;
  padding: 11px 14px;
  margin: 0 0 12px;
}
.notice { color: var(--halo); background: rgba(124, 77, 255, .1); border: 1px solid rgba(167, 139, 250, .25); }
.warning { color: #FFD9A8; background: rgba(255, 170, 80, .08); border: 1px solid rgba(255, 196, 120, .3); }
.warning p, .warning ul { margin: 0; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 0 0 12px;
}

@media (max-width: 560px) {
  .panel { padding: 18px 16px; }
  .kind { min-width: 0; }
}
</style>
