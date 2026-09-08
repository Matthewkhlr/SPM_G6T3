import axiosClient from "./axiosClient";

export const getVenues = () => axiosClient.get("/venues");

export const getVenue = (venueId) => axiosClient.get(`/venues/${venueId}`);
