import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("equipment");

export const getEquipmentList = () => axiosClient.get("/equipment");

export const getEquipment = (equipmentId) => axiosClient.get(`/equipment/${equipmentId}`);

export const createEquipment = (body) => axiosClient.post("/equipment", body);

export const updateEquipment = (equipmentId, body) => axiosClient.patch(`/equipment/${equipmentId}`, body);

export const checkEquipmentAvailability = (body) => axiosClient.post("/equipment/availability", body);

export const getEquipmentActivityLog = (equipmentId) =>
  axiosClient.get(`/equipment/${equipmentId}/activity-log`);
