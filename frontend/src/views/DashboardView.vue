<template>
  <div class="shell">
    <aside class="sidebar">
      <AppLogo dark />

      <nav class="nav">
        <div
          v-for="tab in currentData.tabs"
          :key="tab"
          class="nav-item"
          :class="{ active: activeTab === tab }"
          @click="activeTab = tab"
        >
          {{ tab }}
        </div>
      </nav>

      <div class="sidebar-footer">
        <div class="role-label">Signed in as {{ session.name }} ({{ currentData.label }})</div>
        <button class="logout-btn" @click="logout">Log out</button>
      </div>
    </aside>

    <main class="content">
      <h2>{{ activeTab }}</h2>

      <!-- Each tab renders its own feature-folder component. Anything not -->
      <!-- listed here has no folder yet — that's an honest scope signal,   -->
      <!-- not a bug, for tabs not built this sprint.                      -->
      <DashboardHome v-if="activeTab === 'Dashboard'" :cards="currentData.cards" />
      <VenueCatalogue v-else-if="activeTab === 'Venue Catalogue'" />
      <BrowseEvents v-else-if="activeTab === 'Browse Events'" />

      <div class="not-built" v-else>
        This tab isn't built yet for this sprint — only Dashboard{{ hasVenueTab ? ', Venue Catalogue' : '' }}{{ hasEventsTab ? ', Browse Events' : '' }} are functional.
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import AppLogo from '../components/shared/AppLogo.vue'
import DashboardHome from '../features/dashboard/DashboardHome.vue'
import VenueCatalogue from '../features/venue-catalogue/VenueCatalogue.vue'
import BrowseEvents from '../features/browse-events/BrowseEvents.vue'
import { roles } from '../config/roles.js'
import { session, logoutSession } from '../store/session.js'

const router = useRouter()
const currentData = computed(() => roles[session.role])
const activeTab = ref('Dashboard')

const hasVenueTab = computed(() => currentData.value.tabs.includes('Venue Catalogue'))
const hasEventsTab = computed(() => currentData.value.tabs.includes('Browse Events'))

function logout() {
  logoutSession()
  router.replace('/login')
}
</script>

<style scoped>
.shell { display: flex; min-height: 100vh; }

.sidebar {
  width: 240px;
  flex-shrink: 0;
  background: rgba(11, 5, 26, .55);
  border-right: 1px solid var(--hairline);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  color: var(--text);
  padding: 24px 18px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.nav { display: flex; flex-direction: column; gap: 4px; font-size: 14px; }
.nav-item {
  position: relative;
  padding: 11px 14px;
  border-radius: 10px;
  color: var(--body);
  cursor: pointer;
  transition: background .35s var(--ease-out), color .35s var(--ease-out);
}
.nav-item.active {
  background: linear-gradient(90deg, rgba(124, 77, 255, .3), rgba(124, 77, 255, .06));
  color: var(--text);
  box-shadow: inset 0 0 0 1px rgba(167, 139, 250, .3);
}
.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 22%;
  bottom: 22%;
  width: 2px;
  border-radius: 2px;
  background: var(--iris-soft);
  box-shadow: 0 0 10px var(--iris);
}
.nav-item:hover:not(.active) { background: rgba(255, 255, 255, .04); color: var(--text); }

.sidebar-footer { margin-top: auto; display: flex; flex-direction: column; gap: 12px; }
.role-label { font-size: 11px; line-height: 1.6; color: var(--muted); }
.logout-btn {
  background: none;
  border: 1px solid var(--hairline);
  color: var(--body);
  border-radius: 999px;
  padding: 9px 0;
  font-size: 13px;
  font-family: 'Inter', sans-serif;
  cursor: pointer;
  transition: background .35s var(--ease-out), color .35s var(--ease-out),
              border-color .35s var(--ease-out);
}
.logout-btn:hover {
  background: rgba(167, 139, 250, .1);
  border-color: rgba(167, 139, 250, .4);
  color: var(--text);
}

.content { flex: 1; min-width: 0; padding: 38px 40px; }
.content h2 {
  margin: 0 0 26px;
  font-size: 22px;
  font-weight: 400;
  letter-spacing: -.01em;
}

.not-built {
  color: var(--muted);
  font-size: 14px;
  background: var(--glass);
  border: 1px dashed var(--hairline);
  border-radius: 14px;
  padding: 26px;
}

@media (max-width: 720px) {
  .shell { flex-direction: column; }
  .sidebar { width: 100%; border-right: none; border-bottom: 1px solid var(--hairline); }
  .content { padding: 28px 22px; }
}
</style>
