<template>
  <!-- SPM-68: clarification threads. Only organisers and staff mount this, and
       the server refuses everyone else (AC6). -->
  <section v-if="showPanel" class="panel clarifications" data-testid="clarification-thread">
    <div class="panel-head">
      <h2>Clarifications</h2>
      <button
        v-if="canRaise && !raising"
        type="button"
        class="btn btn-outline small"
        data-testid="clarification-raise"
        @click="openRaise"
      >
        Ask the organiser
      </button>
    </div>
    <p v-if="loadError" class="form-error">{{ loadError }}</p>

    <form v-if="raising" class="raise-form" data-testid="clarification-form" @submit.prevent="submitRaise">
      <label for="clarification-field">About (optional)</label>
      <select id="clarification-field" v-model="field" data-testid="clarification-field">
        <option value="">The request in general</option>
        <option v-for="[key, label] in FIELD_OPTIONS" :key="key" :value="key">{{ label }}</option>
      </select>
      <label for="clarification-message">What is unclear?</label>
      <textarea
        id="clarification-message"
        v-model="message"
        rows="3"
        maxlength="2000"
        data-testid="clarification-message"
      ></textarea>
      <p class="hint">
        The organiser is emailed, and the request waits in Changes Requested until every question is resolved.
      </p>
      <p v-if="raiseError" class="form-error">{{ raiseError }}</p>
      <div class="form-actions">
        <button type="button" class="btn btn-ghost small" @click="raising = false">Cancel</button>
        <button
          type="submit"
          class="btn btn-solid small"
          :disabled="saving || !message.trim()"
          data-testid="clarification-submit"
        >
          {{ saving ? 'Sending…' : 'Send question' }}
        </button>
      </div>
    </form>

    <p v-if="!clarifications.length && !raising && !loadError" class="empty-note">
      No clarifications have been raised.
    </p>

    <article
      v-for="item in clarifications"
      :key="item.clarificationId"
      class="clarification"
      data-testid="clarification-item"
      :data-status="item.status"
    >
      <div class="clarification-head">
        <span v-if="item.field" class="field-chip">{{ fieldLabel(item.field) }}</span>
        <span class="state" :class="item.status">{{ item.status === 'open' ? 'Open' : 'Resolved' }}</span>
        <button
          v-if="isAssignedCoordinator && item.status === 'open'"
          type="button"
          class="btn btn-ghost small resolve"
          :disabled="busy.has(item.clarificationId)"
          data-testid="clarification-resolve"
          @click="resolve(item)"
        >
          Mark resolved
        </button>
      </div>

      <!-- AC3: the question and every reply, in order, each with author, role, and time. -->
      <ol class="entries">
        <li
          v-for="entry in item.entries"
          :key="entry.entryId"
          class="entry"
          :class="entry.authorRole"
          data-testid="clarification-entry"
        >
          <div class="byline">
            <span class="author">{{ entry.authorName || roleLabel(entry.authorRole) }}</span>
            <span class="role">{{ roleLabel(entry.authorRole) }}</span>
            <time :datetime="entry.createdAt">{{ formatUtc(entry.createdAt) }}</time>
          </div>
          <p class="message">{{ entry.message }}</p>
        </li>
      </ol>

      <p v-if="item.status === 'resolved'" class="resolved-note">Resolved {{ formatUtc(item.resolvedAt) }}</p>
      <form v-else-if="canReply" class="reply-form" @submit.prevent="submitReply(item)">
        <label :for="`reply-${item.clarificationId}`" class="visually-hidden">Reply</label>
        <textarea
          :id="`reply-${item.clarificationId}`"
          v-model="replies[item.clarificationId]"
          rows="2"
          maxlength="2000"
          placeholder="Write a reply"
          data-testid="clarification-reply-input"
        ></textarea>
        <div class="form-actions">
          <button
            type="submit"
            class="btn btn-solid small"
            :disabled="busy.has(item.clarificationId) || !(replies[item.clarificationId] || '').trim()"
            data-testid="clarification-reply-submit"
          >
            Reply
          </button>
        </div>
      </form>
      <p v-if="rowErrors[item.clarificationId]" class="form-error">{{ rowErrors[item.clarificationId] }}</p>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  getClarifications,
  raiseClarification,
  replyToClarification,
  resolveClarification,
} from '../../api/eventService.js'
import { FIELD_LABELS, fieldLabel } from '../../config/eventFields.js'
import { IN_REVIEW_EVENT_STATUSES } from '../../config/eventStatus.js'
import { session } from '../../store/session.js'
import { formatUtc } from '../../utils/datetime.js'

const props = defineProps({ event: { type: Object, required: true } })
// Raising or resolving can change the event's status, so the page re-reads it.
const emit = defineEmits(['changed'])

// The request fields a clarification can name (the server checks the same list).
const FIELD_OPTIONS = Object.entries(FIELD_LABELS)
const ROLE_LABELS = { organiser: 'Organiser', coordinator: 'Coordinator' }

const clarifications = ref([])
const loaded = ref(false)
const loadError = ref('')
const raising = ref(false)
const field = ref('')
const message = ref('')
const saving = ref(false)
const raiseError = ref('')
const replies = reactive({})
const rowErrors = reactive({})
const busy = reactive(new Set())

const isAssignedCoordinator = computed(
  () =>
    session.role === 'coordinator' &&
    !!props.event.coordinatorId &&
    props.event.coordinatorId === session.userId,
)
// AC8: never on a draft; and only while the request is still being reviewed.
const canRaise = computed(
  () => isAssignedCoordinator.value && IN_REVIEW_EVENT_STATUSES.includes(props.event.status),
)
// The server also checks the organiser belongs to the event's organisation.
const canReply = computed(() => isAssignedCoordinator.value || session.role === 'organiser')
const showPanel = computed(
  () => loaded.value && (clarifications.value.length > 0 || canRaise.value || !!loadError.value),
)

function roleLabel(role) {
  return ROLE_LABELS[role] || role
}

function errorText(err, fallback) {
  const detail = err.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

function replace(updated) {
  clarifications.value = clarifications.value.map((item) =>
    item.clarificationId === updated.clarificationId ? updated : item,
  )
}

async function load() {
  try {
    const { data } = await getClarifications(props.event.eventId)
    clarifications.value = data
  } catch (err) {
    // A 403 means this viewer may not see threads at all, so show nothing.
    if (err.response?.status !== 403) loadError.value = errorText(err, 'Could not load clarifications.')
  } finally {
    loaded.value = true
  }
}

function openRaise() {
  field.value = ''
  message.value = ''
  raiseError.value = ''
  raising.value = true
}

async function submitRaise() {
  saving.value = true
  raiseError.value = ''
  try {
    const { data } = await raiseClarification(props.event.eventId, message.value, field.value || null)
    clarifications.value = [...clarifications.value, data]
    raising.value = false
    emit('changed')
  } catch (err) {
    raiseError.value = errorText(err, 'Could not send the question. Please try again.')
  } finally {
    saving.value = false
  }
}

async function submitReply(item) {
  const id = item.clarificationId
  busy.add(id)
  delete rowErrors[id]
  try {
    const { data } = await replyToClarification(props.event.eventId, id, replies[id])
    replace(data)
    replies[id] = ''
  } catch (err) {
    rowErrors[id] = errorText(err, 'Could not send the reply. Please try again.')
  } finally {
    busy.delete(id)
  }
}

async function resolve(item) {
  const id = item.clarificationId
  busy.add(id)
  delete rowErrors[id]
  try {
    const { data } = await resolveClarification(props.event.eventId, id)
    replace(data)
    emit('changed')
  } catch (err) {
    rowErrors[id] = errorText(err, 'Could not resolve this clarification. Please try again.')
  } finally {
    busy.delete(id)
  }
}

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
.panel-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 14px; }
.panel h2 { margin: 0; font-size: 16px; font-weight: 500; }
.empty-note { font-size: 14px; color: var(--muted); margin: 0; }
.hint { font-size: 12px; color: var(--muted); margin: -6px 0 12px; line-height: 1.5; }

.btn.small { padding: 7px 14px; font-size: 13px; }
.btn:disabled { opacity: .55; cursor: not-allowed; }

label {
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
  display: block;
  margin-bottom: 6px;
}
.visually-hidden {
  position: absolute; width: 1px; height: 1px; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap;
}
select,
textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  padding: 0 12px;
  height: 42px;
  margin-bottom: 12px;
  font-size: 14px;
  color: var(--text);
  font-family: 'Inter', sans-serif;
}
textarea { height: auto; padding: 10px 12px; resize: vertical; line-height: 1.5; }
select:focus, textarea:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .6);
  box-shadow: 0 0 0 3px rgba(124, 77, 255, .16);
}
select option { background: #1A1030; color: #F3EEFF; }

.raise-form {
  border: 1px solid var(--hairline);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}
.form-actions { display: flex; justify-content: flex-end; gap: 8px; }

.clarification {
  border-top: 1px solid var(--hairline);
  padding: 16px 0 4px;
}
.clarification:first-of-type { border-top: none; padding-top: 0; }
.clarification-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.resolve { margin-left: auto; }
.field-chip,
.state {
  font-size: 10px;
  letter-spacing: .06em;
  text-transform: uppercase;
  border-radius: 999px;
  padding: 2px 9px;
}
.field-chip { color: var(--halo); background: rgba(124, 77, 255, .18); border: 1px solid rgba(167, 139, 250, .3); }
.state.open { color: #FFD9A8; background: rgba(255, 170, 80, .1); border: 1px solid rgba(255, 196, 120, .35); }
.state.resolved { color: var(--muted); border: 1px solid var(--hairline); }

.entries { list-style: none; margin: 0 0 12px; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.entry {
  background: rgba(255, 255, 255, .03);
  border: 1px solid var(--hairline);
  border-radius: 10px;
  padding: 10px 14px;
}
.entry.organiser { margin-left: 24px; }
.byline { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; font-size: 12px; color: var(--muted); }
.author { color: var(--text); font-size: 13px; }
.role { text-transform: uppercase; letter-spacing: .06em; font-size: 10px; }
.message { margin: 6px 0 0; font-size: 14px; line-height: 1.55; color: var(--body); white-space: pre-wrap; word-break: break-word; }
.resolved-note { font-size: 12px; color: var(--muted); margin: 0 0 8px; }

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
  .entry.organiser { margin-left: 12px; }
}
</style>
