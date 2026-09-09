import { reactive } from 'vue'

// Mirrors the signed-in user's backend profile (from GET /users/me), keyed
// off Firebase's own auth state so a page refresh keeps the session — the
// actual authorization check still happens server-side on every request.
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
