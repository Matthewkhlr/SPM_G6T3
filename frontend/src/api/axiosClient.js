import axios from "axios";
import { auth } from "../firebase.js";
import { logoutSession } from "../store/session.js";

const axiosClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

axiosClient.interceptors.request.use(async (config) => {
  // getIdToken() returns the cached token, refreshing it first if expired.
  const token = await auth.currentUser?.getIdToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// A 401 here means the session is no longer valid server-side even though
// the frontend thought it was (revoked token, expired refresh token, clock
// skew, backend restart, ...). Force a clean logout rather than leaving the
// user stuck on a page whose API calls silently keep failing.
axiosClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      logoutSession();
      try {
        await auth.signOut();
      } catch {
        // already signed out — nothing to do
      }
      const { default: router } = await import("../router/index.js");
      if (router.currentRoute.value.name !== "login") {
        router.replace("/login");
      }
    }
    return Promise.reject(error);
  }
);

export default axiosClient;
