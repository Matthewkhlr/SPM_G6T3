import axios from "axios";
import { auth } from "../firebase.js";
import { logoutSession } from "../store/session.js";

const serviceUrls = {
  user: import.meta.env.VITE_USER_SERVICE_URL || "http://localhost:8001",
  event: import.meta.env.VITE_EVENT_SERVICE_URL || "http://localhost:8002",
  venue: import.meta.env.VITE_VENUE_SERVICE_URL || "http://localhost:8003",
  equipment: import.meta.env.VITE_EQUIPMENT_SERVICE_URL || "http://localhost:8004",
  registration: import.meta.env.VITE_REGISTRATION_SERVICE_URL || "http://localhost:8005",
  notification: import.meta.env.VITE_NOTIFICATION_SERVICE_URL || "http://localhost:8006",
};

export function createServiceClient(service) {
  const client = axios.create({ baseURL: serviceUrls[service] });

  client.interceptors.request.use(async (config) => {
    const token = await auth.currentUser?.getIdToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      if (error.response?.status === 401) {
        logoutSession();
        try {
          await auth.signOut();
        } catch {
          // Already signed out.
        }
        const { default: router } = await import("../router/index.js");
        if (router.currentRoute.value.name !== "login") router.replace("/login");
      }
      return Promise.reject(error);
    },
  );

  return client;
}
