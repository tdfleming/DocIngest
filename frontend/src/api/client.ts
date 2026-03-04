import axios from "axios";

const API_KEY_STORAGE_KEY = "docingest_api_key";
const JWT_STORAGE_KEY = "docingest_jwt";

const client = axios.create({
  baseURL: "/v1",
});

client.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem(API_KEY_STORAGE_KEY);
  if (apiKey) {
    config.headers["X-API-Key"] = apiKey;
  }
  const jwt = localStorage.getItem(JWT_STORAGE_KEY);
  if (jwt) {
    config.headers["Authorization"] = `Bearer ${jwt}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      error.config?.url !== "/auth/login" &&
      error.config?.url !== "/auth/status" &&
      error.config?.url !== "/auth/me"
    ) {
      localStorage.removeItem(JWT_STORAGE_KEY);
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export { API_KEY_STORAGE_KEY, JWT_STORAGE_KEY };
export default client;
