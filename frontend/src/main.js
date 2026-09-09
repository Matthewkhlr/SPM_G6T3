import { createApp } from 'vue'
import { onAuthStateChanged } from 'firebase/auth'
import App from './App.vue'
import router from './router'
import './assets/main.css'
import { auth } from './firebase.js'
import { getMe } from './api/userService.js'
import { loginSession, logoutSession } from './store/session.js'

let mounted = false

// Firebase persists its own session across reloads; re-derive our session
// store from it before the router makes its first requiresAuth decision,
// so a refresh doesn't bounce an already-signed-in user back to /login.
onAuthStateChanged(auth, async (user) => {
  if (user) {
    try {
      const { data: profile } = await getMe()
      loginSession({ role: profile.role, name: profile.userName })
    } catch {
      logoutSession()
    }
  } else {
    logoutSession()
  }

  if (!mounted) {
    mounted = true
    createApp(App).use(router).mount('#app')
  }
})
