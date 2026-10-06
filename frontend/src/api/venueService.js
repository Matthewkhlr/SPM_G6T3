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

// SPM-62: anything left out of `body` is taken from the event record.
export const checkSuitability = (eventId, venueId, body = {}) =>
  axiosClient.post("/venues/suitability", { eventId, venueId, ...body });

// SPM-61: `facility` and `accessibility` are lists, sent as repeated keys
// (facility=A&facility=B), which is the form the server reads.
export const searchVenues = (params = {}) =>
  axiosClient.get("/venues/search", { params, paramsSerializer: { indexes: null } });

// SPM-63: venue booking requests.
export const requestVenueBooking = (body) => axiosClient.post("/venues/bookings", body);

export const getVenueBookings = (params = {}) => axiosClient.get("/venues/bookings", { params });

export const withdrawVenueBooking = (bookingId) => axiosClient.post(`/venues/bookings/${bookingId}/withdraw`);
