import axiosClient from "./axiosClient";

export const getUser = (userId) => axiosClient.get(`/users/${userId}`);
export const updateUserProfile = (userId, data) => axiosClient.patch(`/users/${userId}`, data);
export const getUserRole = (userId) => axiosClient.get(`/users/${userId}/role`);