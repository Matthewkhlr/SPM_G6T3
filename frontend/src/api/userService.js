import axiosClient from "./axiosClient";

export const login = (username, password) =>
  axiosClient.post("/users/login", { username, password });

export const getMe = () => axiosClient.get("/users/me");

export const getUsers = () => axiosClient.get("/users");
