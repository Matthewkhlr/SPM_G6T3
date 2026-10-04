import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("notification");

export const sendNotification = (to, subject, body) =>
  axiosClient.post("/notifications", { to, subject, body });

// The signed-in user's own in-app notifications, newest first, one page at a
// time. unreadOnly/page/pageSize all optional - the backend defaults match.
export const getNotifications = ({ unreadOnly, page, pageSize } = {}) =>
  axiosClient.get("/notifications", {
    params: { unreadOnly, page, pageSize },
  });

// For the bell badge - cheaper than fetching the list just to count it.
export const getUnreadNotificationCount = () => axiosClient.get("/notifications/unread-count");

export const markNotificationRead = (notificationId) =>
  axiosClient.post(`/notifications/${notificationId}/read`);

export const markAllNotificationsRead = () => axiosClient.post("/notifications/read-all");
