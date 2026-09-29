<template>
  <section class="equipment-requests">
    <h3>Equipment request</h3>
    <p v-if="loading" class="hint">Loading equipment requests…</p>
    <p v-else-if="loadError" class="form-error">{{ loadError }}</p>
    <template v-else>
      <ul v-if="lines.length" class="lines">
        <li v-for="request in lines" :key="request.requestId">
          <div class="line-main">
            <span class="qty">{{ request.quantity }}</span>
            <span class="name">{{ equipmentName(request.equipmentId) }}</span>
            <span class="status">{{ statusLabel(request.status) }}</span>
          </div>
          <p v-if="request.technicalRequirements" class="notes">{{ request.technicalRequirements }}</p>
        </li>
      </ul>
      <p v-else class="hint">No equipment has been requested for this event yet.</p>
      <div v-if="unavailable.length" class="outcome" data-testid="equipment-request-outcome">
        <p v-for="request in unavailable" :key="request.requestId">
          {{ equipmentName(request.equipmentId) }} ({{ request.equipmentId }}) is unavailable.
          <template v-if="request.reviewNote"> {{ request.reviewNote }}</template>
        </p>
      </div>
      <form v-if="canRecord" class="request-form" @submit.prevent="submit">
        <label>
          Equipment type
          <select v-model="equipmentId" required>
            <option value="" disabled>Select a type</option>
            <option v-for="item in catalogue" :key="item.equipmentId" :value="item.equipmentId">
              {{ item.name }}
            </option>
          </select>
        </label>
        <label>
          Quantity
          <input v-model.number="quantity" type="number" min="1" required />
        </label>
        <label class="wide">
          Technical requirements
          <textarea v-model="technicalRequirements" rows="2" />
        </label>
        <p v-if="saveError" class="form-error">{{ saveError }}</p>
        <div class="actions">
          <button type="submit" class="btn btn-solid small" :disabled="saving || !canUseWindow">
            {{ saving ? 'Saving…' : 'Add to request' }}
          </button>
        </div>
        <p v-if="!canUseWindow" class="hint">This event needs a start and end time before equipment can be requested.</p>
      </form>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { createEquipmentRequest, getEquipmentList, getEquipmentRequests } from '../../api/equipmentService.js'
import { session } from '../../store/session.js'

const props = defineProps({
  event: { type: Object, required: true },
})

const catalogue = ref([])
const requests = ref([])
const loading = ref(true)
const loadError = ref('')
const saveError = ref('')
const saving = ref(false)
const equipmentId = ref('')
const quantity = ref(1)
const technicalRequirements = ref('')

const canRecord = computed(() => session.role === 'coordinator' && props.event.status !== 'draft')
const canUseWindow = computed(() => Boolean(props.event.proposedStartAt && props.event.proposedEndAt))
const lines = computed(() => requests.value.filter((request) => request.eventId === props.event.eventId))
const unavailable = computed(() => lines.value.filter((request) => request.status === 'unavailable'))
const names = computed(() => Object.fromEntries(catalogue.value.map((item) => [item.equipmentId, item.name])))

function equipmentName(id) {
  return names.value[id] || id
}

function statusLabel(status) {
  if (status === 'pending') return 'Requested'
  if (status === 'approved') return 'Accepted'
  if (status === 'reserved') return 'Reserved'
  if (status === 'unavailable') return 'Unavailable'
  if (status === 'rejected') return 'Rejected'
  return status
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const [equipmentList, requestList] = await Promise.all([getEquipmentList(), getEquipmentRequests()])
    catalogue.value = equipmentList.data
    requests.value = requestList.data
  } catch {
    loadError.value = 'Unable to load equipment requests.'
  } finally {
    loading.value = false
  }
}

async function submit() {
  saveError.value = ''
  saving.value = true
  try {
    await createEquipmentRequest({
      eventId: props.event.eventId,
      equipmentId: equipmentId.value,
      quantity: Number(quantity.value) || 1,
      technicalRequirements: technicalRequirements.value.trim(),
      startsAt: props.event.proposedStartAt,
      endsAt: props.event.proposedEndAt,
    })
    equipmentId.value = ''
    quantity.value = 1
    technicalRequirements.value = ''
    await load()
  } catch (err) {
    const detail = err.response?.data?.detail
    saveError.value = typeof detail === 'string' ? detail : 'Unable to add this equipment request.'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.equipment-requests {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 22px 24px;
}
h3 { margin: 0 0 14px; font-size: 16px; font-weight: 500; }
.lines { list-style: none; margin: 0 0 16px; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.lines li {
  background: rgba(255, 255, 255, .03);
  border: 1px solid var(--hairline);
  border-radius: 12px;
  padding: 12px 14px;
}
.line-main { display: flex; align-items: center; gap: 10px; }
.qty {
  min-width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: rgba(124, 77, 255, .18);
  color: var(--halo);
  font-size: 13px;
  font-weight: 600;
}
.name { font-size: 14px; color: var(--text); }
.status {
  margin-left: auto;
  font-size: 11px;
  letter-spacing: .05em;
  text-transform: uppercase;
  color: var(--iris-soft);
}
.notes, .hint { color: var(--muted); font-size: 13px; }
.notes { margin: 8px 0 0; line-height: 1.5; }
.hint { margin: 0 0 14px; }
.outcome {
  margin: 0 0 14px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .3);
}
.outcome p { margin: 0 0 6px; font-size: 14px; line-height: 1.5; }
.outcome p:last-child { margin-bottom: 0; }
.request-form { display: grid; grid-template-columns: 1fr 140px; gap: 12px 16px; }
.wide { grid-column: 1 / -1; }
label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
input, textarea, select {
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: 10px;
  color: var(--text);
  font: inherit;
  font-size: 14px;
  padding: 8px 10px;
}
select option { color: #1b1230; background: #fff; }
.actions { grid-column: 1 / -1; display: flex; justify-content: flex-end; }
.form-error {
  grid-column: 1 / -1;
  margin: 0;
  color: #ff8a76;
  font-size: 13px;
}
@media (max-width: 560px) {
  .request-form { grid-template-columns: 1fr; }
}
</style>
