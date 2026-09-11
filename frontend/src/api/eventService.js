import axiosClient from "./axiosClient";

export const getEvents = () => axiosClient.get("/events");

export const getEvent = (eventId) => axiosClient.get(`/events/${eventId}`);

// organiserId is not sent — the backend takes it from the bearer token.
export const createEvent = (event) => axiosClient.post("/events", event);
