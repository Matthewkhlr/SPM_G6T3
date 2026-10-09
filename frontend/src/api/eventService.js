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

// SPM-69: the assigned coordinator approves; the event moves to planning. The
// note is optional and shown to the organiser. While clarifications are open the
// server answers 409 (detail.requiresConfirmation) until the coordinator confirms.
export const approveEvent = (eventId, note = "", confirmOpenClarifications = false) =>
  axiosClient.post(`/events/${eventId}/approve`, { note, confirmOpenClarifications });

// { decision, decisionNote, decidedBy, decidedAt } — all null until a decision is made.
// Organisers (their own organisation's events) and staff only.
export const getEventDecision = (eventId) => axiosClient.get(`/events/${eventId}/decision`);

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

export const getRequirementOptions = () => axiosClient.get("/events/requirement-options");

export const getOpenEvents = (params = {}) => axiosClient.get("/events/open-for-registration", { params });

export const getOpenEvent = (eventId) => axiosClient.get(`/events/open-for-registration/${eventId}`);

export const getReadiness = (eventId) => axiosClient.get(`/events/${eventId}/readiness`);

export const updateReadinessItem = (eventId, itemId, body) =>
  axiosClient.patch(`/events/${eventId}/readiness-items/${itemId}`, body);

export const saveDraftRequirements = (eventId, body) => axiosClient.patch(`/events/${eventId}`, body);

// SPM-66: coordinators who can be assigned, each with { userId, name, email,
// activeEventCount } — the count is information only, there is no limit.
export const getCoordinatorCandidates = () => axiosClient.get("/events/coordinators");

// Assigning a submitted request moves it to "under review".
export const assignCoordinator = (eventId, coordinatorId) =>
  axiosClient.post(`/events/${eventId}/assign-coordinator`, { coordinatorId });

// { coordinatorId, name, email } — all null until someone is assigned.
// Organisers (their own organisation's events) and staff only.
export const getEventCoordinator = (eventId) => axiosClient.get(`/events/${eventId}/coordinator`);

// SPM-90: the assigned coordinator sets registration needed, period, and capacity
// (send only what changes). A capacity over the booked venue, or turning
// registration off with people registered, comes back as a 409 whose detail
// lists warnings (detail.requiresConfirmation); resend with the matching
// confirmOverVenueCapacity / confirmRegistrationOff once the coordinator agrees.
export const updateRegistrationSettings = (eventId, settings, confirmations = {}) =>
  axiosClient.patch(`/events/${eventId}/registration-settings`, { ...settings, ...confirmations });

// SPM-106: change requests, newest first, each with { status, reason,
// proposedChanges, currentValues, decisionReason }. Organisers (their
// organisation's events) and staff only.
export const getChangeRequests = (eventId) => axiosClient.get(`/events/${eventId}/change-requests`);

// Organiser only. proposedChanges maps field -> proposed value; a reason is required.
export const raiseChangeRequest = (eventId, proposedChanges, reason) =>
  axiosClient.post(`/events/${eventId}/change-requests`, { proposedChanges, reason });

export const withdrawChangeRequest = (eventId, changeRequestId) =>
  axiosClient.post(`/events/${eventId}/change-requests/${changeRequestId}/withdraw`);

// Assigned coordinator only. Accepting applies the values like an edit: a
// significant change comes back as a 409 (detail.requiresConfirmation) until
// confirmSignificantChange is true.
export const acceptChangeRequest = (eventId, changeRequestId, reason = "", confirmSignificantChange = false) =>
  axiosClient.post(`/events/${eventId}/change-requests/${changeRequestId}/accept`, { reason, confirmSignificantChange });

export const declineChangeRequest = (eventId, changeRequestId, reason) =>
  axiosClient.post(`/events/${eventId}/change-requests/${changeRequestId}/decline`, { reason });

// SPM-68: clarification threads — the question, then every reply, each with
// { authorName, authorRole, createdAt }. Organisers (their organisation's
// events) and staff only.
export const getClarifications = (eventId) => axiosClient.get(`/events/${eventId}/clarifications`);

// Assigned coordinator only. field is optional (an event request field name).
// Moves the request to "changes requested" and emails the organiser.
export const raiseClarification = (eventId, message, field = null) =>
  axiosClient.post(`/events/${eventId}/clarifications`, { message, field });

// The organiser (or a colleague) or the assigned coordinator. Returns the whole thread.
export const replyToClarification = (eventId, clarificationId, message) =>
  axiosClient.post(`/events/${eventId}/clarifications/${clarificationId}/reply`, { message });

// Assigned coordinator only. Resolving the last open one returns the request to "under review".
export const resolveClarification = (eventId, clarificationId) =>
  axiosClient.post(`/events/${eventId}/clarifications/${clarificationId}/resolve`);

// Coordinator only — internal notes are never on the shared event read.
export const getInternalNotes = (eventId) => axiosClient.get(`/events/${eventId}/internal-notes`);
// SPM-120: safety review. The assigned coordinator can also submit a planning event, with
// both notes at once, once its venue and equipment are confirmed; a 409 names what is still `missing`.
export const submitSafetyReview = (eventId, crowdMovement, equipmentPlacement = "") =>
  axiosClient.post(`/events/${eventId}/safety-reviews`, { crowdMovement, equipmentPlacement });

// SPM-120, change 6: Venue Staff send the venue arrangements and technical support the
// technical ones. The review opens once every part the event needs is in (`review` is then set).
export const getSafetyHandoff = (eventId) => axiosClient.get(`/events/${eventId}/safety-handoff`);

export const sendVenueArrangements = (eventId, crowdMovement) =>
  axiosClient.post(`/events/${eventId}/safety-handoff/venue`, { crowdMovement });

export const sendTechnicalArrangements = (eventId, equipmentPlacement) =>
  axiosClient.post(`/events/${eventId}/safety-handoff/technical`, { equipmentPlacement });

// Safety Officers only: reviews with this status, longest-waiting first.
export const getSafetyReviewQueue = (status = "pending") =>
  axiosClient.get("/events/safety-reviews", { params: { status } });

// Every review of the event, newest first, each with the facts submitted and the outcome.
export const getSafetyReviews = (eventId) => axiosClient.get(`/events/${eventId}/safety-reviews`);

// Safety Officers only; every other role gets 403.
export const approveSafetyReview = (eventId, reviewId, note = "") =>
  axiosClient.post(`/events/${eventId}/safety-reviews/${reviewId}/approve`, { note });

export const rejectSafetyReview = (eventId, reviewId, reason) =>
  axiosClient.post(`/events/${eventId}/safety-reviews/${reviewId}/reject`, { reason });

// affected: any of "venue", "technical" — flagged for venue staff or technical support to review again.
export const requestSafetyChanges = (eventId, reviewId, requiredChanges, affected = []) =>
  axiosClient.post(`/events/${eventId}/safety-reviews/${reviewId}/request-changes`, { requiredChanges, affected });

// SPM-72: { ready, missing: [{ kind: "venue"|"equipment"|"safety"|"status", message, equipmentId? }] }.
// Assigned coordinator only.
export const getConfirmation = (eventId) => axiosClient.get(`/events/${eventId}/confirmation`);

// Moves the event to Confirmed; a 409 names what is still missing (detail.gaps).
export const confirmEvent = (eventId) => axiosClient.post(`/events/${eventId}/confirm`);

// Record an equipment line as not required (with a reason), or needed again. Planning only.
export const markEquipmentNotRequired = (eventId, equipmentId, reason) =>
  axiosClient.post(`/events/${eventId}/equipment-lines/${equipmentId}/not-required`, { reason });

export const markEquipmentRequired = (eventId, equipmentId) =>
  axiosClient.delete(`/events/${eventId}/equipment-lines/${equipmentId}/not-required`);
