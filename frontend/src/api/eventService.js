import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("event");

export const getEvents = () => axiosClient.get("/events");

// All events except rejected ones.
export const getAllEvents = () => axiosClient.get("/events/all");

// Only events with status "confirmed".
export const getConfirmedEvents = () => axiosClient.get("/events/confirmed");

// Coordinator-only: submitted / under-review / changes-requested events.
// sort: "proposedStartAt" to order by event date instead of wait time.
// assignedTo: a coordinator userId, to see only their own assignments.
export const getSubmissionQueue = ({ sort, assignedTo } = {}) =>
  axiosClient.get("/events/queue", { params: { sort, assignedTo } });

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

// The signed-in organiser's own events at any stage, except ones they discarded.
export const getMyEvents = () => axiosClient.get("/events/mine");

// Only allowed while the event is still a draft — the backend enforces this.
export const discardEvent = (eventId) => axiosClient.delete(`/events/${eventId}`);

export const getActivityLog = (eventId) => axiosClient.get(`/events/${eventId}/activity-log`);

// SPM-71: the assigned coordinator edits an event. Send only the changed fields.
// A significant change on an event with confirmed arrangements comes back as a
// 409 whose detail names them (detail.requiresConfirmation); resend with
// confirmSignificantChange: true once the coordinator has confirmed.
export const updateEvent = (eventId, changes, confirmSignificantChange = false) =>
  axiosClient.patch(`/events/${eventId}`, { ...changes, confirmSignificantChange });

// { fields: [...significant], quietFields: [...] }
export const getSignificantFields = () => axiosClient.get("/events/significant-fields");

// SPM-66: coordinators who can be assigned, each with { userId, name, email,
// activeEventCount } — the count is information only, there is no limit.
export const getCoordinatorCandidates = () => axiosClient.get("/events/coordinators");

// Assigning a submitted request moves it to "under review".
export const assignCoordinator = (eventId, coordinatorId) =>
  axiosClient.post(`/events/${eventId}/assign-coordinator`, { coordinatorId });

// { coordinatorId, name, email } — all null until someone is assigned.
// Organisers (their own organisation's events) and staff only.
export const getEventCoordinator = (eventId) => axiosClient.get(`/events/${eventId}/coordinator`);

// Coordinator only — internal notes are never on the shared event read.
export const getInternalNotes = (eventId) => axiosClient.get(`/events/${eventId}/internal-notes`);