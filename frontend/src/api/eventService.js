// eventService.js
import axiosClient from "./axiosClient";

export const getEvent = (eventId) => axiosClient.get(`/events/${eventId}`);
export const createEvent = (data) => axiosClient.post("/events", data);
export const updateEvent = (eventId, data) => axiosClient.patch(`/events/${eventId}`, data);