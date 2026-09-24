import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("venue");

export const getVenues = (includeRetired = false) =>
  axiosClient.get("/venues", { params: includeRetired ? { includeRetired: true } : {} });

export const getVenue = (venueId) => axiosClient.get(`/venues/${venueId}`);

export const createVenue = (body) => axiosClient.post("/venues", body);

export const updateVenue = (venueId, body) => axiosClient.patch(`/venues/${venueId}`, body);

export const retireVenue = (venueId, confirm = false) =>
  axiosClient.post(`/venues/${venueId}/retire${confirm ? "?confirm=true" : ""}`);

export const getVenueActivityLog = (venueId) => axiosClient.get(`/venues/${venueId}/activity-log`);
