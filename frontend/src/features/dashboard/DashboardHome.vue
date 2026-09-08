<template>
  <div class="card-grid">
    <div v-for="card in cards" :key="card.title" class="card">
      <div class="card-title">{{ card.title }}</div>
      <div class="card-sub">{{ card.sub }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  cards: { type: Array, required: true }
})
</script>

<style scoped>
.card-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.card {
  position: relative;
  overflow: hidden;
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 16px;
  padding: 22px;
  transition: transform .5s var(--ease-out), border-color .5s var(--ease-out),
              background .5s var(--ease-out);
}
/* Faint corner glow that brightens on hover */
.card::after {
  content: '';
  position: absolute;
  top: -40%;
  right: -30%;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(124, 77, 255, .28), transparent 70%);
  opacity: .5;
  transition: opacity .5s var(--ease-out);
  pointer-events: none;
}
.card:hover {
  transform: translateY(-4px);
  border-color: rgba(167, 139, 250, .38);
  background: var(--glass-strong);
}
.card:hover::after { opacity: 1; }

.card-title {
  position: relative;
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 500;
  color: var(--text);
  font-size: 15px;
  margin-bottom: 6px;
}
.card-sub { position: relative; font-size: 14px; line-height: 1.6; color: var(--body); }

@media (max-width: 720px) {
  .card-grid { grid-template-columns: 1fr; }
}
</style>
