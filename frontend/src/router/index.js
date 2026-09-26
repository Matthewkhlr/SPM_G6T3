import { createRouter, createWebHistory } from 'vue-router'
import LandingView from '../views/LandingView.vue'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import EventDetail from '../features/event-detail/EventDetail.vue'
import { session } from '../store/session.js'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'landing', component: LandingView },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/app', name: 'dashboard', component: DashboardView, meta: { requiresAuth: true } },
    {
      path: '/app/events/:id',
      name: 'event-detail',
      component: EventDetail,
      meta: { requiresAuth: true }
    }
  ]
})

// Every request is also independently verified server-side (401 without a
// valid Firebase token) — this guard only covers front-end navigation, so a
// signed-out user never even sees a protected view render.
router.beforeEach((to) => {
  if (to.meta.requiresAuth && !session.isAuthenticated) {
    return { name: 'login' }
  }
  // An already-signed-in user hitting /login goes straight back to their
  // session instead of being shown the login form again.
  if (to.name === 'login' && session.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

export default router
