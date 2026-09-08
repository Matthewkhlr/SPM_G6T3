import axiosClient from "./axiosClient";

export const sendNotification = (to, subject, body) =>
  axiosClient.post("/notifications", { to, subject, body });
