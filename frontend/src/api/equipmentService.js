import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("equipment");

export const getEquipmentList = () => axiosClient.get("/equipment");

export const getEquipment = (equipmentId) => axiosClient.get(`/equipment/${equipmentId}`);

export const createEquipment = (body) => axiosClient.post("/equipment", body);

export const updateEquipment = (equipmentId, body) => axiosClient.patch(`/equipment/${equipmentId}`, body);

export const checkEquipmentAvailability = (body) => axiosClient.post("/equipment/availability", body);

export const getEquipmentRequests = () => axiosClient.get("/equipment/requests");

export const createEquipmentRequest = (body) => axiosClient.post("/equipment/requests", body);

export const refineEquipmentRequest = (requestId, body) =>
  axiosClient.patch(`/equipment/requests/${requestId}/details`, body);

export const reviewEquipmentRequest = (requestId, body) =>
  axiosClient.post(`/equipment/requests/${requestId}/review`, body);

export const reserveEquipmentRequest = (requestId) =>
  axiosClient.post(`/equipment/requests/${requestId}/reserve`);

export const markEquipmentRequestUnavailable = (requestId, body) =>
  axiosClient.post(`/equipment/requests/${requestId}/unavailable`, body);

export const getEquipmentActivityLog = (equipmentId) =>
  axiosClient.get(`/equipment/${equipmentId}/activity-log`);
