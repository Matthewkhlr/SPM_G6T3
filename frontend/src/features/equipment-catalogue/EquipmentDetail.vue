<template>
  <div class="equipment-detail">
    <button type="button" class="btn btn-ghost" @click="router.push('/app')">← Equipment</button>
    <p v-if="loading" class="empty-note">Loading equipment…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <template v-else>
      <h1>{{ equipment.name }}</h1>
      <section data-testid="equipment-reservations">
        <h2>Reservations</h2>
        <p v-for="row in reservations" :key="row.reservationId">
          {{ row.eventId }} · {{ row.quantity }} · {{ row.status }}
        </p>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getEquipment, getEquipmentReservations } from '../../api/equipmentService.js'

const route = useRoute()
const router = useRouter()
const equipment = ref(null)
const reservations = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const item = await getEquipment(route.params.id)
    equipment.value = item.data
    const held = await getEquipmentReservations(route.params.id)
    reservations.value = held.data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load this equipment.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.equipment-detail { display: flex; flex-direction: column; gap: 12px; max-width: 720px; }
</style>
