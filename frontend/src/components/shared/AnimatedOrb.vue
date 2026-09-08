<template>
  <div class="orb-scene" :style="{ '--orb-size': resolvedSize }">
    <div class="orb-atmosphere"></div>

    <div class="orb-float">
      <div v-if="ring" class="orb-ring"></div>
      <div v-if="ring" class="orb-ring orb-ring-2"></div>

      <div class="orb-body">
        <div class="orb-surface"></div>
        <div class="orb-terrain"></div>
        <div class="orb-shading"></div>
        <div class="orb-specular"></div>
      </div>

      <div class="orb-rim"></div>

      <template v-if="nodes">
        <div class="node n1"></div>
        <div class="node n2"></div>
      </template>
    </div>

    <!-- Wordmark / headline sits centred on the sphere, as in the reference art -->
    <div class="orb-content"><slot /></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// A rim-lit planet: a dark violet sphere whose surface scrolls horizontally to
// read as rotation, wrapped in a bright hairline rim and an atmospheric halo.
const props = defineProps({
  // A number is treated as pixels; a string passes straight through, so callers
  // can hand in a fluid value like "clamp(260px, 44vw, 520px)".
  size: { type: [Number, String], default: 420 },
  ring: { type: Boolean, default: true },
  nodes: { type: Boolean, default: true }
})

const resolvedSize = computed(() =>
  typeof props.size === 'number' ? `${props.size}px` : props.size
)
</script>

<style scoped>
.orb-scene {
  position: relative;
  width: var(--orb-size);
  height: var(--orb-size);
  margin: 0 auto;
  display: grid;
  place-items: center;
}

/* ---------- Halo ---------- */

.orb-atmosphere {
  position: absolute;
  inset: -30%;
  border-radius: 50%;
  background:
    radial-gradient(circle, rgba(167, 139, 250, .34) 0%, rgba(124, 77, 255, .16) 42%, transparent 66%);
  filter: blur(30px);
  animation: halo-pulse 7s ease-in-out infinite;
}
@keyframes halo-pulse {
  0%, 100% { transform: scale(1); opacity: .85; }
  50% { transform: scale(1.07); opacity: 1; }
}

.orb-float {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  animation: float 9s ease-in-out infinite;
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-16px); }
}

/* ---------- Sphere ---------- */

.orb-body {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  overflow: hidden;
  background: radial-gradient(circle at 34% 28%, #5A45B8 0%, #37237F 30%, #1F1257 58%, #100833 100%);
}

/* Wide gradient bands scrolled sideways — the illusion of a turning globe */
.orb-surface {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(ellipse 26% 16% at 20% 34%, rgba(139, 92, 246, .5), transparent 70%),
    radial-gradient(ellipse 18% 22% at 46% 62%, rgba(99, 102, 241, .42), transparent 72%),
    radial-gradient(ellipse 22% 12% at 72% 28%, rgba(168, 85, 247, .38), transparent 70%),
    radial-gradient(ellipse 14% 18% at 88% 70%, rgba(56, 224, 200, .2), transparent 72%);
  background-size: 200% 100%;
  background-repeat: repeat-x;
  animation: rotate-surface 42s linear infinite;
}
@keyframes rotate-surface {
  from { background-position-x: 0%; }
  to { background-position-x: 200%; }
}

/* A second, faster layer of fine detail for depth */
.orb-terrain {
  position: absolute;
  inset: 0;
  opacity: .5;
  background-image:
    repeating-linear-gradient(96deg, rgba(233, 224, 255, .05) 0 2px, transparent 2px 26px),
    radial-gradient(ellipse 30% 10% at 60% 46%, rgba(233, 224, 255, .12), transparent 70%);
  background-size: 200% 100%;
  animation: rotate-surface 34s linear infinite;
}

/* Spherical falloff + the terminator that sells the curvature */
.orb-shading {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 34% 28%, transparent 30%, rgba(8, 3, 26, .3) 66%, rgba(5, 1, 16, .72) 100%),
    radial-gradient(circle at 80% 86%, rgba(5, 1, 16, .6), transparent 54%);
}

.orb-specular {
  position: absolute;
  top: 8%;
  left: 14%;
  width: 44%;
  height: 30%;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(233, 224, 255, .3), transparent 68%);
  filter: blur(10px);
  animation: sheen 7s ease-in-out infinite;
}
@keyframes sheen {
  0%, 100% { opacity: .55; }
  50% { opacity: .95; }
}

/* ---------- Rim light ---------- */

.orb-rim {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1px solid rgba(245, 240, 255, .92);
  /* The last inset is offset toward the lower-left so the rim reads as a
     crescent catching light from one side rather than a uniform outline. */
  box-shadow:
    0 0 18px rgba(233, 224, 255, .55),
    0 0 60px rgba(167, 139, 250, .45),
    0 0 130px rgba(124, 77, 255, .35),
    inset 0 0 26px rgba(199, 180, 255, .28),
    inset 10px -10px 40px rgba(214, 200, 255, .28);
  animation: rim-glow 7s ease-in-out infinite;
}
@keyframes rim-glow {
  0%, 100% {
    box-shadow:
      0 0 18px rgba(233, 224, 255, .5),
      0 0 60px rgba(167, 139, 250, .4),
      0 0 130px rgba(124, 77, 255, .3),
      inset 0 0 26px rgba(199, 180, 255, .24),
      inset 10px -10px 40px rgba(214, 200, 255, .24);
  }
  50% {
    box-shadow:
      0 0 26px rgba(233, 224, 255, .75),
      0 0 84px rgba(167, 139, 250, .55),
      0 0 170px rgba(124, 77, 255, .45),
      inset 0 0 34px rgba(199, 180, 255, .38),
      inset 12px -12px 50px rgba(214, 200, 255, .4);
  }
}

/* ---------- Orbits ---------- */

.orb-ring {
  position: absolute;
  width: 128%;
  height: 128%;
  border-radius: 50%;
  border: 1px solid rgba(167, 139, 250, .22);
  transform: rotateX(74deg);
  animation: ring-spin 26s linear infinite;
}
.orb-ring-2 {
  width: 148%;
  height: 148%;
  border-color: rgba(167, 139, 250, .1);
  animation-duration: 40s;
  animation-direction: reverse;
}
@keyframes ring-spin {
  from { transform: rotateX(74deg) rotateZ(0deg); }
  to { transform: rotateX(74deg) rotateZ(360deg); }
}

.node {
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.n1 {
  background: var(--signal);
  box-shadow: 0 0 12px var(--signal);
  animation: orbit-a 26s linear infinite;
}
.n2 {
  background: var(--halo);
  box-shadow: 0 0 12px rgba(233, 224, 255, .9);
  animation: orbit-b 40s linear infinite;
}
@keyframes orbit-a {
  from { transform: rotate(0deg) translateX(calc(var(--orb-size) * .64)) rotate(0deg); }
  to { transform: rotate(360deg) translateX(calc(var(--orb-size) * .64)) rotate(-360deg); }
}
@keyframes orbit-b {
  from { transform: rotate(180deg) translateX(calc(var(--orb-size) * .74)) rotate(-180deg); }
  to { transform: rotate(540deg) translateX(calc(var(--orb-size) * .74)) rotate(-540deg); }
}

/* ---------- Slotted content ---------- */

/* Display type is allowed to run wider than the sphere it sits on, which is the
   look the reference art uses. Centred with a transform rather than by grid
   alignment, because grid clamps an item wider than its track to the start edge. */
.orb-content {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  text-align: center;
  width: max-content;
  max-width: 94vw;
}

@media (prefers-reduced-motion: reduce) {
  .orb-atmosphere, .orb-float, .orb-surface, .orb-terrain,
  .orb-specular, .orb-rim, .orb-ring, .node {
    animation: none !important;
  }
}
</style>
