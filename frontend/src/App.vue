<template>
  <CosmicBackdrop />
  <div class="app-layer">
    <router-view v-slot="{ Component }">
      <transition name="page" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup>
import CosmicBackdrop from './components/shared/CosmicBackdrop.vue'
</script>

<style scoped>
/* Every route renders above the fixed starfield */
.app-layer { position: relative; z-index: 1; }

.page-enter-active,
.page-leave-active {
  transition: opacity .45s var(--ease-out), transform .45s var(--ease-out);
}
.page-enter-from { opacity: 0; transform: translateY(12px); }
.page-leave-to { opacity: 0; transform: translateY(-8px); }

@media (prefers-reduced-motion: reduce) {
  .page-enter-active, .page-leave-active { transition: none; }
}
</style>
