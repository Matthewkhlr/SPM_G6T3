<template>
  <div class="login-split">
    <router-link to="/" class="back-link">← Back</router-link>

    <div class="login-brand">
      <AnimatedOrb size="clamp(200px, 24vw, 300px)" :nodes="false" />
      <p>Coordinators, venue staff, technical support, organisers and attendees — one shared record per event.</p>
    </div>

    <div class="login-form-wrap">
      <form class="login-form glass" @submit.prevent="submit" novalidate>
        <p class="eyebrow">Welcome back</p>
        <h2>Log in</h2>

        <label for="username">Email</label>
        <input id="username" v-model="username" type="text" placeholder="you@connectsphere.com" autocomplete="username" />
        <p v-if="showErrors && !username" class="field-error">Email is required.</p>

        <label for="password">Password</label>
        <div class="password-field">
          <input
            id="password"
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            placeholder="••••••••"
            autocomplete="current-password"
          />
          <button
            type="button"
            class="password-toggle"
            :aria-label="showPassword ? 'Hide password' : 'Show password'"
            @click="showPassword = !showPassword"
          >
            <svg v-if="showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
              <path d="M3 12s3.6-7 9-7 9 7 9 7-3.6 7-9 7-9-7-9-7Z" stroke-linecap="round" stroke-linejoin="round" />
              <circle cx="12" cy="12" r="3" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
              <path d="M3 3l18 18" stroke-linecap="round" />
              <path
                d="M10.6 5.2A9.8 9.8 0 0 1 12 5c5.4 0 9 7 9 7a14.5 14.5 0 0 1-3.1 3.8M6.6 6.6C4.6 8 3 12 3 12s3.6 7 9 7a8.6 8.6 0 0 0 3.4-.7M9.9 9.9a3 3 0 0 0 4.2 4.2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </button>
        </div>
        <p v-if="showErrors && !password" class="field-error">Password is required.</p>

        <p v-if="authError" class="auth-error">{{ authError }}</p>

        <button class="btn btn-solid submit-btn" type="submit" :disabled="isSubmitting">
          {{ isSubmitting ? 'Logging in…' : 'Log in' }}
        </button>

        <details class="demo-creds">
          <summary>Demo credentials (for markers/testing)</summary>
          <ul>
            <li v-for="u in users" :key="u.username">{{ u.role }}: {{ u.username }} / {{ u.password }}</li>
          </ul>
        </details>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { signInWithEmailAndPassword } from 'firebase/auth'
import AnimatedOrb from '../components/shared/AnimatedOrb.vue'
import { auth } from '../firebase.js'
import { users } from '../auth/users.data.js'
import { getMe } from '../api/userService.js'
import { loginSession } from '../store/session.js'

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const showErrors = ref(false)
const authError = ref('')
const isSubmitting = ref(false)
const router = useRouter()

async function submit() {
  authError.value = ''

  // Empty-field validation blocks submission (acceptance criterion).
  if (!username.value || !password.value) {
    showErrors.value = true
    return
  }

  isSubmitting.value = true
  try {
    await signInWithEmailAndPassword(auth, username.value, password.value)
    const { data: profile } = await getMe()
    loginSession({ role: profile.role, name: profile.userName })
    router.push('/app')
  } catch {
    // Generic message on invalid credentials — does not reveal which field was wrong.
    authError.value = 'Invalid email or password.'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.login-split {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 100vh;
  align-items: center;
}

.back-link {
  position: absolute;
  top: 28px;
  left: 32px;
  font-size: 12px;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--muted);
  transition: color .35s var(--ease-out);
}
.back-link:hover { color: var(--text); }

.login-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  text-align: center;
  animation: fade-in 1s var(--ease-out) both;
}
.login-brand p {
  max-width: 320px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--body);
  margin-top: 32px;
}

.login-form-wrap { display: flex; align-items: center; justify-content: center; padding: 40px 24px; }
.login-form {
  width: 100%;
  max-width: 380px;
  border-radius: 20px;
  padding: 36px 34px 32px;
  box-shadow: 0 30px 90px rgba(4, 1, 12, .6);
  animation: fade-in 1s var(--ease-out) .12s both;
}
.login-form h2 { margin: 10px 0 26px; font-size: 26px; font-weight: 400; }

.login-form label {
  font-size: 11px;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--muted);
  display: block;
  margin-bottom: 8px;
}
.login-form input {
  width: 100%;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 10px;
  height: 46px;
  padding: 0 14px;
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--text);
  font-family: 'Inter', sans-serif;
  transition: border-color .35s var(--ease-out), box-shadow .35s var(--ease-out),
              background .35s var(--ease-out);
}
.login-form input::placeholder { color: rgba(203, 188, 240, .35); }
.login-form input:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .6);
  background: rgba(255, 255, 255, .05);
  box-shadow: 0 0 0 3px rgba(124, 77, 255, .16);
}

.password-field { position: relative; display: flex; align-items: center; margin-bottom: 16px; }
.password-field input { padding-right: 44px; margin-bottom: 0; }
.password-toggle {
  position: absolute;
  top: 0;
  bottom: 0;
  right: 6px;
  margin: auto 0;
  height: 30px;
  width: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
  background: transparent;
  border: none;
  border-radius: 8px;
  padding: 0;
  color: #1A1A1A;
  cursor: pointer;
  transition: background .2s var(--ease-out);
}
.password-toggle:hover,
.password-toggle:focus-visible {
  background: rgba(0, 0, 0, .08);
}
.password-toggle svg { width: 17px; height: 17px; }

.submit-btn { width: 100%; padding: 14px; margin-top: 8px; }

.field-error { color: #FF8A76; font-size: 11px; margin: -10px 0 12px; }
.auth-error {
  color: #FF8A76;
  font-size: 13px;
  margin: 4px 0 0;
  padding: 10px 12px;
  border: 1px solid rgba(255, 138, 118, .3);
  border-radius: 8px;
  background: rgba(255, 138, 118, .07);
}


.demo-creds { margin-top: 22px; font-size: 11px; color: var(--muted); }
.demo-creds summary { cursor: pointer; letter-spacing: .04em; }
.demo-creds ul { margin: 10px 0 0; padding-left: 16px; line-height: 1.9; }

@keyframes fade-in {
  from { opacity: 0; transform: translateY(18px); }
  to { opacity: 1; transform: none; }
}

@media (max-width: 860px) {
  .login-split { grid-template-columns: 1fr; padding-top: 60px; }
  .login-brand { padding: 24px; }
  .login-brand p { margin-top: 20px; }
}

@media (prefers-reduced-motion: reduce) {
  .login-brand, .login-form { animation: none; }
}
</style>
