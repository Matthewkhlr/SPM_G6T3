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

// Draft-stage requests — only eventName is required on save (see EventDraftUpsert).
export const saveDraft = (draft) => axiosClient.post("/events/drafts", draft);

export const updateDraft = (eventId, draft) => axiosClient.put(`/events/${eventId}/draft`, draft);

export const getMyDrafts = () => axiosClient.get("/events/drafts/mine");

// Finalizes an existing draft into a fully-validated submitted request (same event id).
export const submitDraft = (eventId, event) => axiosClient.post(`/events/${eventId}/submit`, event);