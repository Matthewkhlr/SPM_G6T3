// axiosClient.js
import axios from "axios";
import { getAuth } from "firebase/auth";

const axiosClient = axios.create({
  baseURL: "http://localhost:8000", // your API Gateway URL
});

axiosClient.interceptors.request.use(async (config) => {
  const user = getAuth().currentUser;
  if (user) {
    const token = await user.getIdToken();
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default axiosClient;