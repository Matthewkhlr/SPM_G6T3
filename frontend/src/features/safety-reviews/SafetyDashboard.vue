<template>
  <!-- SPM-120: the Safety Officer's dashboard. Live counts, every event waiting
       for a review with its key safety facts, and the three decisions inline. -->
  <div class="safety-dashboard" data-testid="safety-dashboard">
    <div class="counts">
      <div v-for="count in COUNTS" :key="count.status" class="count" :data-testid="`safety-count-${count.status}`">
        <span class="count-value">{{ loaded ? lists[count.status].length : '–' }}</span>
        <span class="count-label">{{ count.label }}</span>
      </div>
    </div>

    <p v-if="notice" class="notice" data-testid="safety-dashboard-notice">{{ notice }}</p>
    <p v-if="loadError" class="form-error">{{ loadError }}</p>

    <section class="block">
      <h3>Waiting for your review</h3>
      <p v-if="!loaded" class="empty-note">Loading…</p>
      <p v-else-if="!lists.pending.length" class="empty-note" data-testid="safety-dashboard-empty">
        Nothing is waiting. Events appear here once their venue and equipment are confirmed and the coordinator
        submits them.
      </p>

      <article
        v-for="review in lists.pending"
        :key="review.reviewId"
        class="item"
        :class="{ open: openId === review.reviewId }"
        :data-testid="`safety-dashboard-item-${review.eventId}`"
      >
        <div class="item-head">
          <div class="item-main">
            <span class="item-name">{{ review.package.eventName }}</span>
            <span class="item-meta">
              {{ formatRange(review.package.proposedStartAt, review.package.proposedEndAt) }} ·
              {{ review.package.expectedAttendance }} attendees ·
              {{ venueSummary(review) }}
            </span>
            <span v-if="hasFlag(review)" class="flag">An arrangement is marked for re-checking</span>
          </div>
          <button
            type="button"
            class="btn small"
            :class="openId === review.reviewId ? 'btn-ghost' : 'btn-solid'"
            :data-testid="`safety-dashboard-review-${review.eventId}`"
            @click="toggle(review)"
          >
            {{ openId === review.reviewId ? 'Close' : 'Review' }}
          </button>
        </div>

        <div v-if="openId === review.reviewId" class="review">
          <dl class="facts">
            <template v-for="venue in review.package.venues" :key="venue.venueId">
              <div>
                <dt>Capacity in layout</dt>
                <dd>{{ venue.capacityInLayout }} ({{ venue.layout || 'largest layout' }}) at {{ venue.venueName }}</dd>
              </div>
              <div>
                <dt>Expected attendance</dt>
                <dd :class="{ warn: review.package.expectedAttendance > venue.capacityInLayout }">
                  {{ review.package.expectedAttendance }}
                </dd>
              </div>
              <div class="wide">
                <dt>Emergency access</dt>
                <dd>{{ venue.emergencyAccess || 'Not recorded for this venue' }}</dd>
              </div>
              <div class="wide">
                <dt>Known venue restrictions</dt>
                <dd>{{ venue.restrictions || 'None recorded' }}</dd>
              </div>
              <div v-if="venue.needsReverification" class="wide">
                <dt>Marked for re-checking</dt>
                <dd class="warn">{{ venue.reverificationNote }}</dd>
              </div>
            </template>
            <div class="wide">
              <dt>Accessibility requirements</dt>
              <dd>
                {{ review.package.accessibilityRequirements.join(', ') || 'None' }}
                <template v-if="review.package.accessibilityNote"> · {{ review.package.accessibilityNote }}</template>
              </dd>
            </div>
            <div class="wide">
              <dt>Equipment and placement</dt>
              <dd>
                <template v-if="review.package.equipment.length">
                  {{ review.package.equipment.map((line) => `${line.quantity} × ${line.name}`).join(', ') }} —
                  {{ review.package.equipmentPlacement }}
                </template>
                <template v-else>No equipment requested</template>
              </dd>
            </div>
            <div class="wide">
              <dt>Crowd movement</dt>
              <dd>{{ review.package.crowdMovement }}</dd>
            </div>
          </dl>
          <router-link class="full-link" :to="`/app/events/${review.eventId}`">Open the full event page →</router-link>

          <label :for="`decision-${review.reviewId}`">Notes for the coordinator</label>
          <textarea
            :id="`decision-${review.reviewId}`"
            v-model="decisionText"
            rows="3"
            maxlength="4000"
            placeholder="Optional to approve; required to reject or request changes"
            data-testid="safety-dashboard-text"
          ></textarea>
          <fieldset class="affected">
            <legend>If requesting changes, review again:</legend>
            <label><input v-model="affected" type="checkbox" value="venue" data-testid="safety-dashboard-affected-venue" /> Venue</label>
            <label><input v-model="affected" type="checkbox" value="technical" data-testid="safety-dashboard-affected-technical" /> Equipment</label>
          </fieldset>
          <p v-if="actionError" class="form-error">{{ actionError }}</p>
          <div class="actions">
            <button
              type="button"
              class="btn btn-outline small"
              :disabled="busy || !decisionText.trim()"
              data-testid="safety-dashboard-reject"
              @click="decide(review, 'reject')"
            >
              Reject
            </button>
            <button
              type="button"
              class="btn btn-outline small"
              :disabled="busy || !decisionText.trim()"
              data-testid="safety-dashboard-request-changes"
              @click="decide(review, 'changes')"
            >
              Request changes
            </button>
            <button
              type="button"
              class="btn btn-solid small"
              :disabled="busy"
              data-testid="safety-dashboard-approve"
              @click="decide(review, 'approve')"
            >
              Approve
            </button>
          </div>
        </div>
      </article>
    </section>

    <section v-if="loaded && recent.length" class="block">
      <h3>Recently decided</h3>
      <ul class="recent">
        <li v-for="review in recent" :key="review.reviewId" :data-testid="`safety-dashboard-decided-${review.eventId}`">
          <span class="state" :class="review.status">{{ OUTCOMES[review.status] }}</span>
          <router-link :to="`/app/events/${review.eventId}`">{{ review.package.eventName }}</router-link>
          <span class="muted">{{ formatUtc(review.decidedAt) }}</span>
          <span v-if="review.decisionNote" class="muted note">· {{ review.decisionNote }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  approveSafetyReview,
  getSafetyReviewQueue,
  rejectSafetyReview,
  requestSafetyChanges,
} from '../../api/eventService.js'
import { formatUtc } from '../../utils/datetime.js'

const COUNTS = [
  { status: 'pending', label: 'Waiting for review' },
  { status: 'approved', label: 'Approved' },
  { status: 'changes_requested', label: 'Changes requested' },
  { status: 'rejected', label: 'Rejected' },
]
const OUTCOMES = { approved: 'Approved', changes_requested: 'Changes requested', rejected: 'Rejected' }

const lists = reactive({ pending: [], approved: [], changes_requested: [], rejected: [] })
const loaded = ref(false)
const loadError = ref('')
const openId = ref('')
const decisionText = ref('')
const affected = ref([])
const busy = ref(false)
const actionError = ref('')
const notice = ref('')

// The five most recent decisions of any kind, newest first.
const recent = computed(() =>
  [...lists.approved, ...lists.changes_requested, ...lists.rejected]
    .sort((a, b) => String(b.decidedAt).localeCompare(String(a.decidedAt)))
    .slice(0, 5),
)

function formatRange(start, end) {
  if (!start || !end) return 'Date not set'
  return `${new Date(start).toLocaleString()} – ${new Date(end).toLocaleString()}`
}

function venueSummary(review) {
  return review.package.venues.map((venue) => venue.venueName).join(', ') || 'No venue'
}

function hasFlag(review) {
  const { venues, equipment } = review.package
  return venues.some((venue) => venue.needsReverification) || equipment.some((line) => line.needsReverification)
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
    const results = await Promise.all(COUNTS.map((count) => getSafetyReviewQueue(count.status)))
    COUNTS.forEach((count, index) => {
      lists[count.status] = results[index].data
    })
  } catch (err) {
    loadError.value = errorText(err, 'Could not load the safety reviews. Please try again.')
  } finally {
    loaded.value = true
  }
}

function toggle(review) {
  openId.value = openId.value === review.reviewId ? '' : review.reviewId
  decisionText.value = ''
  affected.value = []
  actionError.value = ''
}

async function decide(review, kind) {
  busy.value = true
  actionError.value = ''
  const name = review.package.eventName
  try {
    if (kind === 'approve') {
      await approveSafetyReview(review.eventId, review.reviewId, decisionText.value)
      notice.value = `Approved ${name}. It moves on to preparation.`
    } else if (kind === 'reject') {
      await rejectSafetyReview(review.eventId, review.reviewId, decisionText.value)
      notice.value = `Rejected ${name}. It is back in planning, and the coordinator and organiser have been told.`
    } else {
      await requestSafetyChanges(review.eventId, review.reviewId, decisionText.value, affected.value)
      notice.value = `Asked for changes to ${name}. It is back in planning until it is submitted again.`
    }
    openId.value = ''
    await load()
  } catch (err) {
    actionError.value = errorText(err, 'Could not record the decision. Please try again.')
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.safety-dashboard { display: flex; flex-direction: column; gap: 18px; max-width: 900px; }

.counts { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.count {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.count-value { font-family: 'Space Grotesk', sans-serif; font-size: 26px; color: var(--text); }
.count-label { font-size: 12px; color: var(--muted); letter-spacing: .04em; }

.block h3 { margin: 0 0 10px; font-size: 15px; font-weight: 500; color: var(--text); }
.empty-note { font-size: 14px; color: var(--muted); margin: 0; line-height: 1.6; }

.item {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 16px 18px;
  margin-bottom: 10px;
}
.item.open { border-color: rgba(167, 139, 250, .38); }
.item-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; }
.item-main { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.item-name { font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 15px; }
.item-meta { font-size: 12px; color: var(--muted); line-height: 1.5; }
.flag {
  align-self: flex-start;
  font-size: 10px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #FFD9A8;
  background: rgba(255, 170, 80, .1);
  border: 1px solid rgba(255, 196, 120, .35);
  border-radius: 999px;
  padding: 2px 9px;
}

.review { border-top: 1px solid var(--hairline); margin-top: 14px; padding-top: 14px; }
.facts { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 20px; margin: 0 0 10px; }
.facts .wide { grid-column: 1 / -1; }
.facts dt, label, legend {
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
}
.facts dd { margin: 3px 0 0; font-size: 14px; color: var(--body); line-height: 1.55; white-space: pre-wrap; }
.facts dd.warn { color: #FFD9A8; }
.full-link { display: inline-block; font-size: 13px; color: var(--halo); margin-bottom: 14px; }

label { display: block; margin-bottom: 6px; }
textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  padding: 10px 12px;
  margin-bottom: 10px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--text);
  font-family: 'Inter', sans-serif;
  resize: vertical;
}
textarea:focus { outline: none; border-color: rgba(167, 139, 250, .6); box-shadow: 0 0 0 3px rgba(124, 77, 255, .16); }
.affected { border: none; padding: 0; margin: 0 0 12px; display: flex; flex-wrap: wrap; gap: 6px 18px; align-items: center; }
.affected legend { padding: 0; margin-bottom: 6px; }
.affected label { display: flex; align-items: center; gap: 8px; margin: 0; font-size: 13px; letter-spacing: 0; text-transform: none; color: var(--body); }
.actions { display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.btn.small { padding: 7px 14px; font-size: 13px; }
.btn:disabled { opacity: .55; cursor: not-allowed; }

.recent { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.recent li { font-size: 13px; color: var(--body); display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; }
.recent a { color: var(--text); }
.muted { color: var(--muted); }
.note { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 360px; }
.state { font-size: 10px; letter-spacing: .06em; text-transform: uppercase; border-radius: 999px; padding: 2px 9px; border: 1px solid var(--hairline); }
.state.approved { color: var(--halo); background: rgba(124, 77, 255, .18); border-color: rgba(167, 139, 250, .3); }
.state.changes_requested { color: #FFD9A8; background: rgba(255, 170, 80, .1); border-color: rgba(255, 196, 120, .35); }
.state.rejected { color: #FF8A76; background: rgba(255, 138, 118, .08); border-color: rgba(255, 138, 118, .3); }

.notice {
  font-size: 13px;
  line-height: 1.6;
  color: var(--halo);
  background: rgba(124, 77, 255, .1);
  border: 1px solid rgba(167, 139, 250, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 0;
}
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 0 0 10px;
}

@media (max-width: 720px) {
  .counts { grid-template-columns: 1fr 1fr; }
  .facts { grid-template-columns: 1fr; }
  .item-head { flex-direction: column; }
}
</style>
