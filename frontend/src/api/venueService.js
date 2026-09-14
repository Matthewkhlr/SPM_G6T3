import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("venue");

export const getVenues = () => axiosClient.get("/venues");

export const getVenue = (venueId) => axiosClient.get(`/venues/${venueId}`);
