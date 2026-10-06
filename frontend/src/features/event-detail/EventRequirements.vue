<template>
  <section class="panel" data-testid="event-requirements">
    <h2>Venue, access, and equipment</h2>
    <p v-if="loading" class="hint">Loading requirement lists…</p>
    <form v-else @submit.prevent="save">
      <label for="layout-preference">Room layout</label>
      <select id="layout-preference" v-model="form.layoutPreference" data-testid="layout-preference">
        <option v-for="layout in options.layouts" :key="layout" :value="layout">{{ layout }}</option>
      </select>

      <label for="preferred-location">Preferred location or region</label>
      <input id="preferred-location" v-model.trim="form.preferredLocation" type="text" data-testid="preferred-location" />

      <fieldset>
        <legend>Facilities</legend>
        <label v-for="facility in options.facilities" :key="facility" class="check">
          <input v-model="form.requiredFacilities" type="checkbox" :value="facility" />
          {{ facility }}
        </label>
      </fieldset>

      <fieldset>
        <legend>Accessibility</legend>
        <label v-for="need in options.accessibility" :key="need" class="check">
          <input v-model="form.accessibilityNeeds" type="checkbox" :value="need" />
          {{ need }}
        </label>
        <label for="accessibility-note">Anything not listed</label>
        <input id="accessibility-note" v-model.trim="form.accessibilityNote" type="text" data-testid="accessibility-note" />
      </fieldset>

      <div class="lines">
        <h3>Equipment</h3>
        <div v-for="(line, index) in form.equipmentLines" :key="index" class="line">
          <select v-model="line.equipmentId" required>
            <option value="" disabled>Type</option>
            <option v-for="item in catalogue" :key="item.equipmentId" :value="item.equipmentId">
              {{ item.name }}
            </option>
          </select>
          <input v-model.number="line.quantity" type="number" min="1" step="1" required />
          <input v-model.trim="line.technicalNotes" type="text" placeholder="Technical notes" />
          <button type="button" class="btn btn-ghost small" @click="form.equipmentLines.splice(index, 1)">Remove</button>
        </div>
        <button type="button" class="btn btn-outline small" @click="addLine">Add equipment</button>
      </div>

      <p v-if="error" class="form-error">{{ error }}</p>
      <button class="btn btn-solid" type="submit" data-testid="event-save-draft" :disabled="saving">
        {{ saving ? 'Saving…' : 'Save draft' }}
      </button>
    </form>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getRequirementOptions, saveDraftRequirements } from '../../api/eventService.js'
import { getEquipmentList } from '../../api/equipmentService.js'

const props = defineProps({
  event: { type: Object, required: true }
})
const emit = defineEmits(['saved'])

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const catalogue = ref([])
const options = reactive({ layouts: [], facilities: [], accessibility: [] })
const form = reactive({
  layoutPreference: props.event.layoutPreference || 'No preference',
  preferredLocation: props.event.preferredLocation || '',
  requiredFacilities: [...(props.event.requiredFacilities || [])],
  accessibilityNeeds: [...(props.event.accessibilitySelections || [])],
  accessibilityNote: props.event.accessibilityNote || '',
  equipmentLines: (props.event.equipmentLines || []).map((line) => ({
    equipmentId: line.equipmentId,
    quantity: line.quantity,
    technicalNotes: line.technicalNotes || ''
  }))
})

function addLine() {
  form.equipmentLines.push({ equipmentId: '', quantity: 1, technicalNotes: '' })
}

onMounted(async () => {
  try {
    const [lists, stock] = await Promise.all([
      getRequirementOptions(),
      getEquipmentList().catch(() => ({ data: [] }))
    ])
    options.layouts = lists.data.layouts || []
    options.facilities = lists.data.facilities || []
    options.accessibility = lists.data.accessibility || []
    catalogue.value = stock.data || []
    if (!options.layouts.includes(form.layoutPreference) && options.layouts.length) {
      form.layoutPreference = options.layouts.includes('No preference') ? 'No preference' : options.layouts[0]
    }
  } catch (err) {
    error.value = 'Could not load the requirement lists.'
  } finally {
    loading.value = false
  }
})

async function save() {
  saving.value = true
  error.value = ''
  try {
    const { data } = await saveDraftRequirements(props.event.eventId, {
      layoutPreference: form.layoutPreference,
      preferredLocation: form.preferredLocation,
      requiredFacilities: form.requiredFacilities,
      accessibilityNeeds: form.accessibilityNeeds,
      accessibilityNote: form.accessibilityNote,
      equipmentLines: form.equipmentLines.filter((line) => line.equipmentId)
    })
    emit('saved', data)
  } catch (err) {
    const detail = err.response?.data?.detail
    error.value = typeof detail === 'string' ? detail : 'Check the equipment quantities and try again.'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.panel { margin-top: 18px; }
.hint, .form-error { font-size: 13px; color: var(--muted); }
.form-error { color: #ff8a76; }
label, legend { display: block; margin-top: 12px; font-size: 13px; color: var(--muted); }
input, select { width: 100%; margin-top: 4px; }
.check { display: flex; gap: 8px; align-items: center; margin-top: 6px; }
.check input { width: auto; }
.line { display: grid; grid-template-columns: 1.4fr 0.6fr 1.4fr auto; gap: 8px; margin-top: 8px; }
.lines { margin: 16px 0; }
button[type='submit'] { margin-top: 16px; }
</style>
