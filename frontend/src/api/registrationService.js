import axiosClient from "./axiosClient";

export const getRegistrationSettings = (eventId) => axiosClient.get(`/registrations/${eventId}`);
export const registerAttendee = (data) => axiosClient.post("/registrations/attendees", data);
export const getAttendeeRegistration = (registrationId) =>
  axiosClient.get(`/registrations/attendees/${registrationId}`);
export const updateAttendeeStatus = (registrationId, status) =>
  axiosClient.patch(`/registrations/attendees/${registrationId}`, { status });