<template>
  <div class="backdrop" aria-hidden="true">
    <div class="nebula n-core"></div>
    <div class="nebula n-left"></div>
    <div class="nebula n-right"></div>
    <canvas ref="canvasEl" class="starfield"></canvas>
    <div class="grain"></div>
    <div class="vignette"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  // Stars per million pixels — keeps density consistent across screen sizes.
  density: { type: Number, default: 90 },
  // Stars drift toward the pointer by this fraction of its offset.
  parallax: { type: Number, default: 0.02 }
})

const canvasEl = ref(null)

let ctx = null
let frame = 0
let stars = []
let width = 0
let height = 0
let dpr = 1
let pointerX = 0
let pointerY = 0
let driftX = 0
let driftY = 0
let reduced = false

function buildStars() {
  const count = Math.round((width * height) / 1_000_000 * props.density)
  stars = Array.from({ length: count }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    // Three depth bands: distant dust, mid stars, a few bright foreground ones.
    depth: Math.random() < 0.75 ? 0.35 : Math.random() < 0.85 ? 0.7 : 1,
    radius: 0.4 + Math.random() * 1.1,
    phase: Math.random() * Math.PI * 2,
    speed: 0.4 + Math.random() * 1.4
  }))
}

function resize() {
  const canvas = canvasEl.value
  if (!canvas) return
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  width = window.innerWidth
  height = window.innerHeight
  canvas.width = width * dpr
  canvas.height = height * dpr
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  buildStars()
  if (reduced) draw(0)
}

function draw(time) {
  ctx.clearRect(0, 0, width, height)

  // Ease the parallax offset toward the pointer so motion never snaps.
  driftX += (pointerX - driftX) * 0.04
  driftY += (pointerY - driftY) * 0.04

  for (const star of stars) {
    const twinkle = reduced ? 0.75 : 0.55 + Math.sin(time / 1000 * star.speed + star.phase) * 0.45
    const x = star.x + driftX * star.depth
    const y = star.y + driftY * star.depth

    ctx.beginPath()
    ctx.arc(x, y, star.radius * star.depth, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(233, 224, 255, ${twinkle * star.depth})`
    ctx.fill()

    // Bright foreground stars get a soft bloom around them.
    if (star.depth === 1) {
      ctx.beginPath()
      ctx.arc(x, y, star.radius * 3.4, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(167, 139, 250, ${twinkle * 0.12})`
      ctx.fill()
    }
  }
}

function loop(time) {
  draw(time)
  frame = requestAnimationFrame(loop)
}

function onPointerMove(event) {
  pointerX = (event.clientX - window.innerWidth / 2) * props.parallax
  pointerY = (event.clientY - window.innerHeight / 2) * props.parallax
}

onMounted(() => {
  ctx = canvasEl.value.getContext('2d')
  reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  resize()
  window.addEventListener('resize', resize)
  if (!reduced) {
    window.addEventListener('pointermove', onPointerMove)
    frame = requestAnimationFrame(loop)
  }
})

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  window.removeEventListener('resize', resize)
  window.removeEventListener('pointermove', onPointerMove)
})
</script>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
  background:
    radial-gradient(120% 80% at 50% 0%, #2E1163 0%, #1A0940 38%, #0B0520 70%, var(--void) 100%);
}

/* Slow-drifting colour clouds layered over the base gradient */
.nebula {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  will-change: transform, opacity;
}
.n-core {
  top: -22vh; left: 50%; width: 90vw; max-width: 1100px; height: 90vh;
  transform: translateX(-50%);
  background: radial-gradient(circle, rgba(124, 77, 255, .5), rgba(124, 77, 255, 0) 65%);
  animation: breathe 16s ease-in-out infinite;
}
.n-left {
  top: 18vh; left: -18vw; width: 60vw; height: 60vh;
  background: radial-gradient(circle, rgba(198, 88, 224, .3), rgba(198, 88, 224, 0) 65%);
  animation: drift-left 26s ease-in-out infinite;
}
.n-right {
  bottom: -12vh; right: -14vw; width: 62vw; height: 62vh;
  background: radial-gradient(circle, rgba(91, 74, 214, .28), rgba(91, 74, 214, 0) 65%);
  animation: drift-right 32s ease-in-out infinite;
}

@keyframes breathe {
  0%, 100% { transform: translateX(-50%) scale(1); opacity: .9; }
  50% { transform: translateX(-50%) scale(1.12); opacity: 1; }
}
@keyframes drift-left {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(6vw, -5vh); }
}
@keyframes drift-right {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(-5vw, 4vh); }
}

.starfield { position: absolute; inset: 0; }

/* Fine film grain keeps the large gradients from banding */
.grain {
  position: absolute;
  inset: -50%;
  opacity: .16;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  animation: shift 8s steps(6) infinite;
}
@keyframes shift {
  0% { transform: translate(0, 0); }
  25% { transform: translate(-2%, 1%); }
  50% { transform: translate(1%, -2%); }
  75% { transform: translate(2%, 2%); }
  100% { transform: translate(0, 0); }
}

.vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(120% 90% at 50% 40%, transparent 40%, rgba(4, 1, 12, .75) 100%);
}

@media (prefers-reduced-motion: reduce) {
  .nebula, .grain { animation: none; }
}
</style>
