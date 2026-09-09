import { initializeApp } from 'firebase/app'
import { browserLocalPersistence, getAuth, setPersistence } from 'firebase/auth'

export const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || ''
}

const app = initializeApp(firebaseConfig)
export const auth = getAuth(app)

// Explicit rather than relying on the SDK default: the session survives
// closing the browser/tab, so a returning user stays signed in.
setPersistence(auth, browserLocalPersistence)
