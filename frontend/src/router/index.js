import { createRouter, createWebHistory } from 'vue-router'
import LandingView from '../views/LandingView.vue'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import { session } from '../store/session.js'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'landing', component: LandingView },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/app', name: 'dashboard', component: DashboardView, meta: { requiresAuth: true } }
  ]
})

// Client-side stand-in for "accessing a protected route without a session
// redirects to login". A real backend would additionally return 401 on the
// API call itself — this guard only covers front-end navigation.
router.beforeEach((to) => {
  if (to.meta.requiresAuth && !session.isAuthenticated) {
    return { name: 'login' }
  }
})

export default router
