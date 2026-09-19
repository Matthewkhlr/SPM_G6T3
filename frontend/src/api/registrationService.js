import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("registration");

export const getRegistrations = (eventId) =>
  axiosClient.get("/registrations", { params: { eventId } });

export const registerForEvent = (eventId, name, email) =>
  axiosClient.post("/registrations", { eventId, name, email });
