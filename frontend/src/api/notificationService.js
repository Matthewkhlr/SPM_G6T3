import axiosClient from "./axiosClient";

export const sendNotification = (data) => axiosClient.post("/notifications", data);
export const getNotificationHistory = (userId) => axiosClient.get(`/notifications/user/${userId}`);