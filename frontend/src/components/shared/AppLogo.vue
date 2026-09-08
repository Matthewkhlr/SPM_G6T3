<template>
  <div class="logo">
    <span class="mark">
      <svg viewBox="0 0 26 26">
        <defs>
          <radialGradient id="logo-fill" cx="34%" cy="28%">
            <stop offset="0%" stop-color="#5B32B0" />
            <stop offset="60%" stop-color="#1E0F47" />
            <stop offset="100%" stop-color="#0B0522" />
          </radialGradient>
        </defs>
        <circle cx="13" cy="13" r="10.5" fill="url(#logo-fill)" stroke="rgba(245,240,255,.9)" stroke-width="1" />
        <ellipse cx="13" cy="13" rx="10.5" ry="4" fill="none" stroke="rgba(167,139,250,.55)" stroke-width=".8" />
      </svg>
    </span>
    <span class="wordmark">ConnectSphere</span>
  </div>
</template>

<script setup>
// `dark` is kept for callers written against the old light theme; the cosmic
// palette is already dark, so the mark renders the same either way.
defineProps({ dark: { type: Boolean, default: false } })
</script>

<style scoped>
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: 'Space Grotesk', sans-serif;
  color: var(--text);
}

.mark {
  display: grid;
  place-items: center;
  filter: drop-shadow(0 0 8px rgba(167, 139, 250, .6));
}
.mark svg { width: 22px; height: 22px; display: block; }

.wordmark {
  font-size: 13px;
  font-weight: 500;
  letter-spacing: .16em;
  text-transform: uppercase;
}
</style>
