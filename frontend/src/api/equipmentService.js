import axiosClient from "./axiosClient";

export const getEquipmentList = () => axiosClient.get("/equipment");
export const getEquipmentUnits = (equipmentId) => axiosClient.get(`/equipment/${equipmentId}/units`);
export const createEquipmentRequest = (data) => axiosClient.post("/equipment/requests", data);
export const updateEquipmentRequestStatus = (requestId, status) =>
  axiosClient.patch(`/equipment/requests/${requestId}`, { status });