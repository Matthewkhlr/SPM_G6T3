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
        <input id="password" v-model="password" type="password" placeholder="••••••••" autocomplete="current-password" />
        <p v-if="showErrors && !password" class="field-error">Password is required.</p>

        <p v-if="authError" class="auth-error">{{ authError }}</p>

        <button class="btn btn-solid submit-btn" type="submit">
          Log in
        </button>

        <p class="hint">No account? <span class="link">Sign up as Event Organiser</span></p>
        <p class="tbd">Internal-staff account provisioning — TBD in customer Q&amp;A</p>

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
import AnimatedOrb from '../components/shared/AnimatedOrb.vue'
import { users, findUser } from '../auth/users.data.js'
import { loginSession } from '../store/session.js'

const username = ref('')
const password = ref('')
const showErrors = ref(false)
const authError = ref('')
const router = useRouter()

function submit() {
  authError.value = ''

  // Empty-field validation blocks submission (acceptance criterion).
  if (!username.value || !password.value) {
    showErrors.value = true
    return
  }

  const user = findUser(username.value, password.value)
  if (!user) {
    // Generic message on invalid credentials — does not reveal which field was wrong.
    authError.value = 'Invalid email or password.'
    return
  }

  loginSession(user)
  router.push('/app')
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

.hint { font-size: 12px; text-align: center; color: var(--muted); margin-top: 18px; }
.link { color: var(--iris-soft); cursor: pointer; }
.tbd { font-size: 11px; text-align: center; color: rgba(203, 188, 240, .3); margin-top: 14px; }

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
