<template>
  <div class="registration-page">
    <button type="button" class="btn btn-ghost back" @click="goBack">← My Registrations</button>

    <p v-if="loading" class="empty-note">Loading registration…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>

    <template v-else-if="registration">
      <header class="page-head">
        <div>
          <p class="eyebrow">Registration</p>
          <h1>{{ eventName }}</h1>
          <span class="status-pill" :class="registration.status">{{ registration.status }}</span>
        </div>
        <button
          v-if="canWithdraw"
          type="button"
          class="btn btn-outline"
          data-testid="registration-withdraw"
          @click="confirming = true"
        >
          Withdraw
        </button>
      </header>

      <p v-if="registration.status === 'withdrawn'" class="confirmation" data-testid="withdraw-confirmation">
        Your registration is withdrawn. Your place has been released.
      </p>

      <section class="panel">
        <dl class="facts">
          <div>
            <dt>Name</dt>
            <dd>{{ registration.attendeeName }}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{{ registration.attendeeEmail }}</dd>
          </div>
        </dl>
      </section>

      <p v-if="withdrawError" class="form-error">{{ withdrawError }}</p>
    </template>

    <div v-if="confirming" class="modal-backdrop" data-testid="withdraw-confirm">
      <div class="modal" role="dialog" aria-modal="true">
        <h3>Withdraw Registration</h3>
        <p>Withdraw from {{ eventName }}? Your place will be released for another attendee.</p>
        <div class="modal-actions">
          <button type="button" class="btn btn-ghost" @click="confirming = false">Stay</button>
          <button type="button" class="btn btn-solid" :disabled="withdrawing" @click="confirmWithdraw">
            Withdraw
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getEvent } from '../../api/eventService.js'
import { getRegistration, withdrawRegistration } from '../../api/registrationService.js'

const route = useRoute()
const router = useRouter()

const registration = ref(null)
const event = ref(null)
const loading = ref(true)
const error = ref('')
const confirming = ref(false)
const withdrawing = ref(false)
const withdrawError = ref('')

const eventName = computed(() => event.value?.eventName || 'this event')

const canWithdraw = computed(() => {
  const row = registration.value
  const current = event.value
  if (!row || row.status !== 'registered' || !current) return false
  const status = String(current.status || '').toLowerCase()
  if (status === 'completed' || status === 'cancelled') return false
  if (!current.proposedStartAt) return false
  return new Date(current.proposedStartAt).getTime() > Date.now()
})

function detail(err, fallback) {
  const message = err.response?.data?.detail
  return typeof message === 'string' ? message : fallback
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await getRegistration(route.params.id)
    registration.value = response.data
  } catch (err) {
    error.value = detail(err, 'Could not load this registration.')
    loading.value = false
    return
  }
  try {
    const response = await getEvent(registration.value.eventId)
    event.value = response.data
  } catch {
    event.value = null
  }
  loading.value = false
}

async function confirmWithdraw() {
  withdrawing.value = true
  withdrawError.value = ''
  try {
    const response = await withdrawRegistration(registration.value.attendeeRegistrationId)
    registration.value = response.data
    confirming.value = false
  } catch (err) {
    withdrawError.value = detail(err, 'Could not withdraw this registration.')
    confirming.value = false
  } finally {
    withdrawing.value = false
  }
}

function goBack() {
  router.push({ path: '/app', query: { tab: 'My Registrations' } })
}

onMounted(load)
</script>

<style scoped>
.registration-page {
  max-width: 760px;
  margin: 0 auto;
  padding: 28px 32px 48px;
}
.back { margin: 0 0 18px -18px; padding-left: 18px; }
.empty-note { font-size: 14px; color: var(--muted); }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin-top: 16px;
}
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 20px;
  margin-bottom: 22px;
}
.page-head h1 { margin: 6px 0 10px; font-size: 28px; font-weight: 500; letter-spacing: -.02em; }
.eyebrow {
  margin: 0;
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
}
.status-pill {
  display: inline-block;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--halo);
  background: rgba(124, 77, 255, .18);
  border: 1px solid rgba(167, 139, 250, .3);
  border-radius: 999px;
  padding: 3px 10px;
}
.status-pill.withdrawn {
  color: #FFB4A8;
  background: rgba(255, 138, 118, .12);
  border-color: rgba(255, 138, 118, .35);
}
.confirmation {
  margin: 0 0 18px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text);
}
.panel {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 22px 24px;
}
.facts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px 20px; margin: 0; }
.facts dt {
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 4px;
}
.facts dd { margin: 0; font-size: 14px; color: var(--body); }
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(5, 2, 14, .7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.modal {
  background: linear-gradient(160deg, #1A0C3B, #0D0524);
  border: 1px solid rgba(167, 139, 250, .28);
  border-radius: 18px;
  padding: 30px;
  width: 380px;
}
.modal h3 { margin: 0 0 14px; font-size: 18px; font-weight: 500; }
.modal p { font-size: 14px; line-height: 1.7; color: var(--body); margin: 0; text-align: center; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.btn:disabled { opacity: .55; cursor: progress; }
@media (max-width: 860px) {
  .registration-page { padding: 22px 18px 36px; }
  .page-head { flex-direction: column; align-items: stretch; }
  .facts { grid-template-columns: 1fr; }
  .back { margin-left: 0; }
}
</style>
