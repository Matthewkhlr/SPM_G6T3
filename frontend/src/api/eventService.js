import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("event");

export const getEvents = () => axiosClient.get("/events");

// All events except rejected ones.
export const getAllEvents = () => axiosClient.get("/events/all");

// Only events with status "confirmed".
export const getConfirmedEvents = () => axiosClient.get("/events/confirmed");

export const getEvent = (eventId) => axiosClient.get(`/events/${eventId}`);

// organiserId is not sent — the backend takes it from the bearer token.
export const createEvent = (event) => axiosClient.post("/events", event);

export const approveEvent = (eventId, reason) =>
  axiosClient.post(`/events/${eventId}/approve`, { reason });

export const rejectEvent = (eventId, reason) =>
  axiosClient.post(`/events/${eventId}/reject`, { reason });