<template>
  <div class="profile">
    <p v-if="loading" class="empty-note">Loading your profile…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>

    <section v-else class="panel">
      <p class="eyebrow">Account</p>
      <h3>{{ profile.userName }}</h3>
      <dl class="facts">
        <div>
          <dt>Email</dt>
          <dd>{{ profile.email }}</dd>
        </div>
        <div>
          <dt>Role</dt>
          <dd>{{ roleLabel }}</dd>
        </div>
        <div v-if="profile.organisationId">
          <dt>Organisation</dt>
          <dd>{{ organisationName }}</dd>
        </div>
      </dl>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getMe, getOrganisations } from '../../api/userService.js'
import { roles } from '../../config/roles.js'

const profile = ref(null)
const organisationName = ref('')
const loading = ref(true)
const error = ref('')

const roleLabel = computed(() => roles[profile.value?.role]?.label || profile.value?.role || '')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getMe()
    profile.value = data
    if (!data.organisationId) return
    organisationName.value = data.organisationId
    try {
      const { data: organisations } = await getOrganisations()
      const match = organisations.find((item) => item.organisationId === data.organisationId)
      if (match?.name) organisationName.value = match.name
    } catch {
      organisationName.value = data.organisationId
    }
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load your profile. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.profile { max-width: 640px; }
.empty-note { font-size: 14px; color: var(--muted); margin: 0; }
.form-error {
  color: #ff8a76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
}
.panel {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 22px 24px;
}
.panel h3 { margin: 8px 0 18px; font-size: 22px; font-weight: 500; }
.facts { display: grid; gap: 16px; margin: 0; }
.facts dt {
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 4px;
}
.facts dd { margin: 0; font-size: 14px; color: var(--body); }
</style>
