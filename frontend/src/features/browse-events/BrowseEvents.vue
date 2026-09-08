<template>
  <div class="registration">
    <div v-for="event in events" :key="event.id" class="event-card">
      <div class="event-head">
        <div>
          <div class="event-name">{{ event.name }}</div>
          <div class="event-meta">
            Status: {{ event.status }} · {{ event.registeredCount }}/{{ event.capacity }} registered
          </div>
        </div>
        <button
          class="btn"
          :class="eligibility(event).eligible ? 'btn-solid' : 'btn-disabled'"
          :disabled="!eligibility(event).eligible || registeredIds.has(event.id)"
          @click="openForm(event)"
        >
          {{ registeredIds.has(event.id) ? 'Registered' : 'Register' }}
        </button>
      </div>
      <div v-if="!eligibility(event).eligible && !registeredIds.has(event.id)" class="ineligible-reason">
        {{ eligibility(event).reason }}
      </div>
    </div>

    <!-- Registration form modal -->
    <div v-if="activeEvent" class="modal-backdrop" @click.self="activeEvent = null">
      <div class="modal">
        <h3>Register for {{ activeEvent.name }}</h3>
        <label>Full name</label>
        <input v-model="form.name" type="text" placeholder="Your name" />
        <p v-if="submitted && !form.name" class="field-error">Name is required.</p>

        <label>Email</label>
        <input v-model="form.email" type="email" placeholder="you@email.com" />
        <p v-if="submitted && !form.email" class="field-error">Email is required.</p>

        <div class="modal-actions">
          <button class="btn btn-outline" @click="activeEvent = null">Cancel</button>
          <button class="btn btn-solid" @click="submitRegistration">Submit</button>
        </div>
      </div>
    </div>

    <!-- Confirmation -->
    <div v-if="confirmedEvent" class="modal-backdrop" @click.self="confirmedEvent = null">
      <div class="modal confirm">
        <h3>You're registered</h3>
        <p>Your registration for <strong>{{ confirmedEvent.name }}</strong> was successful. A confirmation has been sent to {{ form.email }}.</p>
        <button class="btn btn-solid" @click="confirmedEvent = null">Done</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { events, registrationEligibility } from './events.data.js'

function eligibility(event) {
  return registrationEligibility(event)
}

const registeredIds = ref(new Set())
const activeEvent = ref(null)
const confirmedEvent = ref(null)
const submitted = ref(false)
const form = reactive({ name: '', email: '' })

function openForm(event) {
  submitted.value = false
  form.name = ''
  form.email = ''
  activeEvent.value = event
}

function submitRegistration() {
  submitted.value = true
  if (!form.name || !form.email) return // required registration info (acceptance criterion)

  // Hardcoded "success": in a real build this hits the API, which re-checks
  // eligibility server-side (capacity can change between page load and submit).
  const event = activeEvent.value
  event.registeredCount += 1
  registeredIds.value.add(event.id)
  confirmedEvent.value = event
  activeEvent.value = null
}
</script>

<style scoped>
.registration { display: flex; flex-direction: column; gap: 12px; }
.event-card {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 18px 20px;
  transition: border-color .4s var(--ease-out), background .4s var(--ease-out);
}
.event-card:hover { border-color: rgba(167, 139, 250, .3); background: var(--glass-strong); }
.event-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.event-name { font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 15px; }
.event-meta { font-size: 12px; margin-top: 4px; text-transform: capitalize; color: var(--muted); }
.ineligible-reason { font-size: 12px; color: #FF8A76; margin-top: 10px; }

.btn-disabled {
  background: rgba(255, 255, 255, .05);
  border: 1px solid var(--hairline);
  color: rgba(203, 188, 240, .4);
  padding: 9px 20px;
  border-radius: 999px;
  cursor: not-allowed;
}

.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(5, 2, 14, .7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center; z-index: 10;
  animation: fade .3s var(--ease-out);
}
.modal {
  background: linear-gradient(160deg, #1A0C3B, #0D0524);
  border: 1px solid rgba(167, 139, 250, .28);
  box-shadow: 0 30px 90px rgba(4, 1, 12, .7), 0 0 60px rgba(124, 77, 255, .18);
  border-radius: 18px;
  padding: 30px;
  width: 340px;
  animation: pop .4s var(--ease-out);
}
.modal.confirm p { font-size: 14px; line-height: 1.7; margin: 12px 0 22px; color: var(--body); }
.modal h3 { margin: 0 0 20px; font-size: 18px; font-weight: 500; }
.modal label {
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); display: block; margin-bottom: 6px;
}
.modal input {
  width: 100%;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  height: 42px;
  padding: 0 12px;
  margin-bottom: 14px;
  font-size: 14px;
  color: var(--text);
  font-family: 'Inter', sans-serif;
  transition: border-color .35s var(--ease-out), box-shadow .35s var(--ease-out);
}
.modal input::placeholder { color: rgba(203, 188, 240, .32); }
.modal input:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .6);
  box-shadow: 0 0 0 3px rgba(124, 77, 255, .16);
}
.field-error { color: #FF8A76; font-size: 11px; margin: -10px 0 10px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }

@keyframes fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes pop {
  from { opacity: 0; transform: translateY(14px) scale(.97); }
  to { opacity: 1; transform: none; }
}

@media (prefers-reduced-motion: reduce) {
  .modal-backdrop, .modal { animation: none; }
}
</style>
