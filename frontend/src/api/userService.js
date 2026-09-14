import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("user");

export const getMe = () => axiosClient.get("/users/me");

export const getUsers = () => axiosClient.get("/users");
