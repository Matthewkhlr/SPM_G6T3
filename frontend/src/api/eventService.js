import axiosClient from "./axiosClient";

export const getEvents = () => axiosClient.get("/events");

export const getEvent = (eventId) => axiosClient.get(`/events/${eventId}`);
