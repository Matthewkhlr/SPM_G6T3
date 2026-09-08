// v-reveal — fades an element up the first time it scrolls into view.
// Usage: <div v-reveal>…</div> or <div v-reveal="120"> for a 120ms stagger delay.

const supportsObserver = typeof IntersectionObserver !== 'undefined'

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

const observer = supportsObserver
  ? new IntersectionObserver(
      entries => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          entry.target.classList.add('is-revealed')
          observer.unobserve(entry.target) // reveal once, then stop watching
        }
      },
      { threshold: 0.15, rootMargin: '0px 0px -8% 0px' }
    )
  : null

export const vReveal = {
  mounted(el, binding) {
    el.setAttribute('data-reveal', '')

    if (!observer || prefersReducedMotion()) {
      el.classList.add('is-revealed')
      return
    }

    if (binding.value) el.style.setProperty('--reveal-delay', `${binding.value}ms`)
    observer.observe(el)
  },
  unmounted(el) {
    observer?.unobserve(el)
  }
}
