<template>
  <div class="log">
    <p v-if="loading" class="hint">Loading the activity log…</p>
    <p v-else-if="error" class="hint error">{{ error }}</p>
    <p v-else-if="!entries.length" class="hint">No quantity changes recorded yet.</p>
    <ul v-else>
      <li v-for="entry in entries" :key="entry.logId">
        <div class="when">{{ entry.action }} · {{ entry.changedByName || entry.changedBy }}</div>
        <div class="change">{{ summarise(entry.changes) }}</div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { getEquipmentActivityLog } from '../../api/equipmentService.js'

const props = defineProps({
  equipmentId: { type: String, required: true },
})

const entries = ref([])
const loading = ref(true)
const error = ref('')

function summarise(changes) {
  if (!changes) return ''
  return Object.entries(changes)
    .map(([field, change]) => `${field}: ${change.old ?? 'none'} → ${JSON.stringify(change.new)}`)
    .join('; ')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getEquipmentActivityLog(props.equipmentId)
    entries.value = data
  } catch {
    error.value = 'Unable to load the activity log.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.equipmentId, load)
</script>

<style scoped>
.log { margin-top: 18px; }
.hint { margin: 0; font-size: 13px; color: var(--muted); }
.hint.error { color: #FF8A76; }
ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
li { border-top: 1px solid var(--hairline); padding-top: 10px; }
.when { font-size: 12px; color: var(--muted); }
.change { font-size: 13px; color: var(--body); margin-top: 4px; }
</style>
