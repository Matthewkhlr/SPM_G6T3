import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("registration");

export const getRegistrationRoster = (eventId) =>
  axiosClient.get("/registrations", { params: { eventId, includeWithdrawn: true } });

export const registerForEvent = (eventId, name, email) =>
  axiosClient.post("/registrations", { eventId, name, email });
