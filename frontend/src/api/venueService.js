import axiosClient from "./axiosClient";

export const getVenues = () => axiosClient.get("/venues");
export const getVenue = (venueId) => axiosClient.get(`/venues/${venueId}`);
export const createVenueBooking = (data) => axiosClient.post("/venues/bookings", data);
export const getVenueBooking = (bookingId) => axiosClient.get(`/venues/bookings/${bookingId}`);
export const updateVenueBookingStatus = (bookingId, status) =>
  axiosClient.patch(`/venues/bookings/${bookingId}`, { status });