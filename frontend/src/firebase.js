// Initialize Firebase here when this folder is ported into the event-platform repo.
// import { initializeApp } from "firebase/app";
// import { getAuth } from "firebase/auth";

export const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "",
};

export function initFirebase() {
  return null;
}
