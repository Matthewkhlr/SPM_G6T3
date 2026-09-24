<template>
  <form class="item-detail" @submit.prevent="submit">
    <div class="detail-header">
      <h3>{{ mode === 'create' ? 'Add equipment' : 'Edit equipment' }}</h3>
    </div>
    <div class="fields">
      <label>Code<input v-model="form.code" required /></label>
      <label>Name<input v-model="form.name" required /></label>
      <label>Category<input v-model="form.category" required /></label>
      <label>Total owned<input v-model.number="form.totalQuantity" type="number" min="0" required /></label>
      <label class="wide">Description<textarea v-model="form.description" rows="2" /></label>
      <label>Home location<input v-model="form.homeLocation" /></label>
      <label>Damaged<input v-model.number="form.damaged" type="number" min="0" /></label>
      <label>Under maintenance<input v-model.number="form.maintenance" type="number" min="0" /></label>
      <label>Retired<input v-model.number="form.retired" type="number" min="0" /></label>
      <label class="wide">Technical notes<textarea v-model="form.technicalNotes" rows="2" /></label>
    </div>
    <p v-if="warning" class="warning">{{ warning }}</p>
    <div class="actions">
      <button type="button" class="btn btn-ghost small" @click="$emit('cancel')">Cancel</button>
      <button v-if="warning" type="button" class="btn btn-solid small" @click="submit(true)">Save anyway</button>
      <button v-else type="submit" class="btn btn-solid small">Save</button>
    </div>
  </form>
</template>

<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  mode: { type: String, required: true },
  equipment: { type: Object, default: null },
  warning: { type: String, default: '' },
})
const emit = defineEmits(['save', 'cancel'])

const form = reactive(blank())

function blank() {
  return {
    code: '',
    name: '',
    category: '',
    description: '',
    homeLocation: '',
    technicalNotes: '',
    totalQuantity: 0,
    damaged: 0,
    maintenance: 0,
    retired: 0,
  }
}

function fill(equipment) {
  form.code = equipment?.code || ''
  form.name = equipment?.name || ''
  form.category = equipment?.category || ''
  form.description = equipment?.description || ''
  form.homeLocation = equipment?.homeLocation || ''
  form.technicalNotes = equipment?.technicalNotes || ''
  form.totalQuantity = equipment?.totalQuantity || 0
  form.damaged = equipment?.outOfService?.damaged || 0
  form.maintenance = equipment?.outOfService?.maintenance || 0
  form.retired = equipment?.outOfService?.retired || 0
}

watch(() => [props.mode, props.equipment], () => {
  if (props.mode === 'edit') fill(props.equipment)
  else Object.assign(form, blank())
}, { immediate: true })

function submit(acknowledge = false) {
  emit('save', {
    code: form.code.trim(),
    name: form.name.trim(),
    category: form.category.trim(),
    description: form.description.trim(),
    homeLocation: form.homeLocation.trim(),
    technicalNotes: form.technicalNotes.trim(),
    totalQuantity: Number(form.totalQuantity) || 0,
    outOfService: {
      damaged: Number(form.damaged) || 0,
      maintenance: Number(form.maintenance) || 0,
      retired: Number(form.retired) || 0,
    },
    acknowledgeReservationImpact: acknowledge === true,
  })
}
</script>

<style scoped>
.item-detail {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 16px;
  padding: 26px;
}
.detail-header { margin-bottom: 16px; }
h3 { margin: 0; font-size: 19px; font-weight: 500; }
.fields { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; }
.wide { grid-column: 1 / -1; }
label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
input, textarea {
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: 10px;
  color: var(--text);
  font: inherit;
  font-size: 14px;
  padding: 8px 10px;
}
.warning {
  margin: 16px 0 0;
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .3);
  color: var(--text);
  font-size: 13px;
  line-height: 1.5;
}
.actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
@media (max-width: 720px) {
  .fields { grid-template-columns: 1fr; }
}
</style>
