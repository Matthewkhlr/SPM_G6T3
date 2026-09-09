import axiosClient from "./axiosClient";

export const getMe = () => axiosClient.get("/users/me");

export const getUsers = () => axiosClient.get("/users");
