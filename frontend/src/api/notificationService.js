import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("notification");

export const sendNotification = (to, subject, body) =>
  axiosClient.post("/notifications", { to, subject, body });
