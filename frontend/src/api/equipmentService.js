import axiosClient from "./axiosClient";

export const getEquipment = () => axiosClient.get("/equipment");

export const getEquipmentItem = (equipmentId) =>
  axiosClient.get(`/equipment/${equipmentId}`);
