import { reactive } from 'vue'

// Front-end-only session stand-in. A real build would store a token (not the
// role itself) and verify it against the server on every protected request —
// this only guards client-side navigation.
export const session = reactive({
  isAuthenticated: false,
  role: null,
  name: null
})

export function loginSession(user) {
  session.isAuthenticated = true
  session.role = user.role
  session.name = user.name
}

export function logoutSession() {
  session.isAuthenticated = false
  session.role = null
  session.name = null
}
