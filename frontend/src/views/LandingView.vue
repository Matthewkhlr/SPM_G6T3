<template>
  <div class="landing">
    <header class="site-header" :class="{ condensed: scrolled }">
      <AppLogo />
      <nav class="site-nav">
        <a href="#capabilities">Capabilities</a>
        <a href="#process">Process</a>
        <a href="#roles">Roles</a>
      </nav>
      <div class="actions">
        <router-link to="/login" class="btn btn-ghost">Log in</router-link>
        <router-link to="/login" class="btn btn-solid">Get started</router-link>
      </div>
    </header>

    <!-- ---------- Hero ---------- -->
    <section class="hero">
      <div class="hero-orb" :style="parallax">
        <AnimatedOrb size="clamp(280px, 44vw, 520px)">
          <p class="eyebrow enter" style="--d: 200ms">Event operations, unified</p>
          <h1 class="wordmark enter" style="--d: 340ms">CONNECTSPHERE</h1>
        </AnimatedOrb>
      </div>

      <div class="hero-copy">
        <p class="hero-tagline enter" style="--d: 700ms">
          Requests, venues, equipment and registrations — held in one orbit
          instead of scattered across inboxes and spreadsheets.
        </p>
        <div class="hero-actions enter" style="--d: 860ms">
          <router-link to="/login" class="btn btn-solid hero-cta">Enter the platform</router-link>
          <a href="#capabilities" class="btn btn-outline">See how it works</a>
        </div>
      </div>

      <a href="#capabilities" class="scroll-cue enter" style="--d: 1100ms">
        <span class="cue-label">Scroll</span>
        <span class="cue-line"></span>
      </a>
    </section>

    <!-- ---------- Marquee ---------- -->
    <div class="marquee" aria-hidden="true">
      <div class="marquee-track">
        <span v-for="n in 2" :key="n" class="marquee-group">
          <span v-for="word in marqueeWords" :key="word + n">
            {{ word }}<i class="dot"></i>
          </span>
        </span>
      </div>
    </div>

    <!-- ---------- Capabilities ---------- -->
    <section id="capabilities" class="section">
      <div class="section-head">
        <p class="eyebrow" v-reveal>What ConnectSphere coordinates</p>
        <h2 class="section-title" v-reveal="80">
          Four moving parts,<br />one shared record
        </h2>
      </div>

      <div class="rows">
        <article
          v-for="(item, i) in offerings"
          :key="item.name"
          class="row"
          v-reveal="i * 110"
        >
          <span class="row-index">{{ String(i + 1).padStart(2, '0') }}</span>
          <span class="row-name">{{ item.name }}</span>
          <span class="row-desc">{{ item.desc }}</span>
          <span class="row-arrow">→</span>
        </article>
      </div>
    </section>

    <!-- ---------- Process ---------- -->
    <section id="process" class="section">
      <div class="section-head">
        <p class="eyebrow" v-reveal>How it works</p>
        <h2 class="section-title" v-reveal="80">From request to check-in</h2>
      </div>

      <div class="steps">
        <article
          v-for="(step, i) in steps"
          :key="step.title"
          class="step glass"
          v-reveal="i * 130"
        >
          <span class="step-index">{{ String(i + 1).padStart(2, '0') }}</span>
          <h3>{{ step.title }}</h3>
          <p>{{ step.detail }}</p>
        </article>
      </div>
    </section>

    <!-- ---------- Roles ---------- -->
    <section id="roles" class="section">
      <div class="section-head">
        <p class="eyebrow" v-reveal>Built for every seat</p>
        <h2 class="section-title" v-reveal="80">Five roles, one source of truth</h2>
      </div>

      <div class="roles">
        <span v-for="(role, i) in roleNames" :key="role" class="role-chip" v-reveal="i * 70">
          {{ role }}
        </span>
      </div>
    </section>

    <!-- ---------- Closing CTA ---------- -->
    <section class="cta" v-reveal>
      <div class="cta-glow"></div>
      <h2>Bring every event into one view</h2>
      <p>Sign in with a demo role and walk the full coordination flow.</p>
      <router-link to="/login" class="btn btn-solid hero-cta">Get started</router-link>
    </section>

    <footer class="site-footer">
      <AppLogo />
      <span class="footer-note">Hardcoded layout — not wired to a backend</span>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import AppLogo from '../components/shared/AppLogo.vue'
import AnimatedOrb from '../components/shared/AnimatedOrb.vue'
import { vReveal } from '../composables/reveal.js'

// Hardcoded content — swap for real copy once the customer confirms release-1 scope.
const offerings = [
  { name: 'Event requests & approvals', desc: 'From first draft to coordinator sign-off' },
  { name: 'Venue availability & booking', desc: 'Search, hold, and confirm the right space' },
  { name: 'Equipment & technical support', desc: 'Reserve gear without double-booking it' },
  { name: 'Attendee registration', desc: 'Capacity, waitlists, and check-in in one flow' }
]

const steps = [
  { title: 'Submit', detail: 'An organiser files the event request with dates, scale and requirements attached.' },
  { title: 'Coordinate', detail: 'Coordinators match the request to a venue, reserve equipment and route approvals.' },
  { title: 'Confirm', detail: 'Venue and technical staff acknowledge their slot; the record locks to a schedule.' },
  { title: 'Run', detail: 'Attendees register against live capacity and arrive to a checked-in door list.' }
]

const roleNames = ['Coordinator', 'Venue staff', 'Technical support', 'Organiser', 'Attendee']

const marqueeWords = ['Venues', 'Equipment', 'Approvals', 'Registrations', 'Scheduling', 'Capacity']

/* Header condenses and the hero drifts as the page scrolls. */
const scrollY = ref(0)
const scrolled = computed(() => scrollY.value > 24)
const parallax = computed(() => ({
  transform: `translate3d(0, ${scrollY.value * 0.18}px, 0)`,
  opacity: Math.max(0, 1 - scrollY.value / 620)
}))

let ticking = false
function onScroll() {
  if (ticking) return
  ticking = true
  requestAnimationFrame(() => {
    scrollY.value = window.scrollY
    ticking = false
  })
}

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))
</script>

<style scoped>
.landing { position: relative; }

/* ---------- Header ---------- */

.site-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 26px 48px;
  transition: padding .5s var(--ease-out), background .5s var(--ease-out),
              border-color .5s var(--ease-out), backdrop-filter .5s var(--ease-out);
  border-bottom: 1px solid transparent;
  animation: fade-down .9s var(--ease-out) both;
}
.site-header.condensed {
  padding: 14px 48px;
  background: rgba(9, 4, 22, .6);
  border-bottom-color: var(--hairline);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.site-nav { display: flex; gap: 34px; font-size: 13px; letter-spacing: .04em; }
.site-nav a { position: relative; color: var(--body); transition: color .35s var(--ease-out); }
.site-nav a::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: -6px;
  width: 100%;
  height: 1px;
  background: var(--iris-soft);
  transform: scaleX(0);
  transform-origin: right;
  transition: transform .45s var(--ease-out);
}
.site-nav a:hover { color: var(--text); }
.site-nav a:hover::after { transform: scaleX(1); transform-origin: left; }

.actions { display: flex; align-items: center; gap: 10px; }

/* ---------- Hero ---------- */

.hero {
  position: relative;
  /* The orb's halo and orbit rings intentionally run past the viewport on
     narrow screens; clip so they can't widen the page. */
  overflow-x: clip;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 120px 24px 80px;
}

.hero-orb { will-change: transform, opacity; }

/* Sits on top of the lit sphere, so it needs more weight than the page default */
.hero-orb .eyebrow {
  margin: 0;
  color: rgba(233, 224, 255, .82);
  text-shadow: 0 0 20px rgba(12, 4, 30, .9);
}

.wordmark {
  margin: 14px 0 0;
  font-weight: 300;
  font-size: clamp(24px, 6.4vw, 82px);
  letter-spacing: clamp(.14em, .5vw, .4em);
  /* Tracking is added after the last glyph too, so nudge back to optical centre */
  text-indent: clamp(.14em, .5vw, .4em);
  line-height: 1;
  white-space: nowrap;
  color: #FFF;
  text-shadow: 0 0 30px rgba(199, 180, 255, .55), 0 0 80px rgba(124, 77, 255, .4);
}

.hero-copy {
  position: relative;
  z-index: 3;
  margin-top: clamp(24px, 5vw, 56px);
  text-align: center;
  max-width: 560px;
}
.hero-tagline {
  font-size: 15px;
  line-height: 1.75;
  color: var(--body);
  margin: 0 0 30px;
}
.hero-actions { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; }
.hero-cta { padding: 14px 32px; font-size: 14px; }

.scroll-cue {
  position: absolute;
  bottom: 34px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}
.cue-label {
  font-size: 10px;
  letter-spacing: .3em;
  text-transform: uppercase;
  color: var(--muted);
}
.cue-line {
  width: 1px;
  height: 46px;
  background: linear-gradient(to bottom, var(--iris-soft), transparent);
  transform-origin: top;
  animation: cue 2.4s ease-in-out infinite;
}
@keyframes cue {
  0%, 100% { transform: scaleY(.4); opacity: .4; }
  50% { transform: scaleY(1); opacity: 1; }
}

/* ---------- Marquee ---------- */

.marquee {
  overflow: hidden;
  border-top: 1px solid var(--hairline);
  border-bottom: 1px solid var(--hairline);
  padding: 18px 0;
  mask-image: linear-gradient(to right, transparent, #000 12%, #000 88%, transparent);
  -webkit-mask-image: linear-gradient(to right, transparent, #000 12%, #000 88%, transparent);
}
.marquee-track { display: flex; width: max-content; animation: slide 34s linear infinite; }
.marquee-group { display: flex; }
.marquee-group > span {
  display: inline-flex;
  align-items: center;
  gap: 26px;
  padding-right: 26px;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 13px;
  letter-spacing: .26em;
  text-transform: uppercase;
  color: var(--muted);
  white-space: nowrap;
}
.dot { width: 4px; height: 4px; border-radius: 50%; background: var(--iris); }
@keyframes slide {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

/* ---------- Sections ---------- */

.section {
  position: relative;
  max-width: 1080px;
  margin: 0 auto;
  padding: clamp(80px, 12vw, 150px) 48px 0;
}
.section-head { margin-bottom: 48px; }
.section-title {
  margin: 14px 0 0;
  font-size: clamp(26px, 3.6vw, 40px);
  font-weight: 400;
  line-height: 1.25;
  letter-spacing: -.01em;
}

/* Capability rows */
.rows { border-top: 1px solid var(--hairline); }
.row {
  position: relative;
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) minmax(0, 1fr) 28px;
  align-items: center;
  gap: 20px;
  padding: 26px 12px;
  border-bottom: 1px solid var(--hairline);
  cursor: default;
  transition: background .5s var(--ease-out), padding-left .5s var(--ease-out);
}
.row::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(to bottom, transparent, var(--iris-soft), transparent);
  opacity: 0;
  transition: opacity .5s var(--ease-out);
}
.row:hover {
  background: linear-gradient(90deg, rgba(124, 77, 255, .1), transparent 70%);
  padding-left: 24px;
}
.row:hover::before { opacity: 1; }

.row-index {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 12px;
  letter-spacing: .1em;
  color: var(--muted);
}
.row-name {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(16px, 2vw, 20px);
  color: var(--text);
  font-weight: 400;
}
.row-desc { font-size: 14px; line-height: 1.6; color: var(--body); }
.row-arrow {
  text-align: right;
  color: var(--iris-soft);
  opacity: 0;
  transform: translateX(-8px);
  transition: opacity .45s var(--ease-out), transform .45s var(--ease-out);
}
.row:hover .row-arrow { opacity: 1; transform: none; }

/* Process steps */
.steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 16px;
}
.step {
  border-radius: 16px;
  padding: 26px 22px 28px;
  transition: transform .5s var(--ease-out), border-color .5s var(--ease-out),
              background .5s var(--ease-out);
}
.step:hover {
  transform: translateY(-6px);
  border-color: rgba(167, 139, 250, .4);
  background: var(--glass-strong);
}
.step-index {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 11px;
  letter-spacing: .2em;
  color: var(--iris-soft);
}
.step h3 { margin: 16px 0 10px; font-size: 17px; font-weight: 500; }
.step p { margin: 0; font-size: 13.5px; line-height: 1.7; color: var(--body); }

/* Roles */
.roles { display: flex; flex-wrap: wrap; gap: 12px; }
.role-chip {
  padding: 11px 22px;
  border: 1px solid var(--hairline);
  border-radius: 999px;
  font-size: 13px;
  letter-spacing: .06em;
  color: var(--body);
  background: rgba(255, 255, 255, .02);
  transition: color .4s var(--ease-out), border-color .4s var(--ease-out),
              box-shadow .4s var(--ease-out), transform .4s var(--ease-out);
}
.role-chip:hover {
  color: var(--text);
  border-color: rgba(167, 139, 250, .5);
  box-shadow: 0 0 24px rgba(124, 77, 255, .3);
  transform: translateY(-2px);
}

/* ---------- CTA ---------- */

.cta {
  position: relative;
  max-width: 1080px;
  margin: clamp(90px, 13vw, 160px) auto 0;
  padding: clamp(60px, 9vw, 96px) 32px;
  text-align: center;
  overflow: hidden;
}
.cta-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 620px;
  height: 400px;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle, rgba(124, 77, 255, .3), transparent 65%);
  filter: blur(50px);
  pointer-events: none;
}
.cta h2 {
  position: relative;
  margin: 0 0 12px;
  font-size: clamp(24px, 3.4vw, 38px);
  font-weight: 400;
}
.cta p { position: relative; margin: 0 0 28px; font-size: 14px; color: var(--body); }
.cta .btn { position: relative; }

/* ---------- Footer ---------- */

.site-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  max-width: 1080px;
  margin: clamp(60px, 8vw, 100px) auto 0;
  padding: 28px 48px 40px;
  border-top: 1px solid var(--hairline);
}
.footer-note { font-size: 12px; color: var(--muted); }

/* ---------- Entrance ---------- */

.enter { animation: rise 1.1s var(--ease-out) both; animation-delay: var(--d, 0ms); }
@keyframes rise {
  from { opacity: 0; transform: translateY(24px); filter: blur(6px); }
  to { opacity: 1; transform: none; filter: blur(0); }
}
@keyframes fade-down {
  from { opacity: 0; transform: translateY(-16px); }
  to { opacity: 1; transform: none; }
}

/* ---------- Responsive ---------- */

@media (max-width: 860px) {
  .site-header, .site-header.condensed { padding: 16px 22px; }
  .site-nav { display: none; }
  .section { padding-left: 22px; padding-right: 22px; }
  .site-footer { padding: 26px 22px 36px; }
  .row {
    grid-template-columns: 40px minmax(0, 1fr);
    row-gap: 6px;
    padding: 20px 8px;
  }
  .row-desc { grid-column: 2; }
  .row-arrow { display: none; }
}

@media (prefers-reduced-motion: reduce) {
  .enter, .site-header, .cue-line, .marquee-track { animation: none; }
  .hero-orb { transform: none !important; opacity: 1 !important; }
}
</style>
