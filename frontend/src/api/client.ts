import axios from "axios";

const API_KEY_STORAGE_KEY = "docingest_api_key";

const client = axios.create({
  baseURL: "/v1",
});

client.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem(API_KEY_STORAGE_KEY);
  if (apiKey) {
    config.headers["X-API-Key"] = apiKey;
  }
  return config;
});

export { API_KEY_STORAGE_KEY };
export default client;
