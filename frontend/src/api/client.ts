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
    // The app has two independent auth schemes: JWT (Authorization: Bearer) for
    // /auth/* endpoints, and the API key (X-API-Key) for documents/search/graph.
    // Only a 401 from a JWT endpoint means the login session expired — that's the
    // only case where we should drop the JWT and bounce to /login. A 401 from an
    // API-key endpoint just means the stored API key is missing/invalid and must
    // NOT tear down a valid login session. (/auth/login, /auth/status, /auth/me
    // legitimately 401 during the unauthenticated boot probe, so exclude them.)
    const url: string = error.config?.url ?? "";
    const isJwtSessionEndpoint =
      url.startsWith("/auth/") &&
      url !== "/auth/login" &&
      url !== "/auth/status" &&
      url !== "/auth/me";

    if (error.response?.status === 401 && isJwtSessionEndpoint) {
      localStorage.removeItem(JWT_STORAGE_KEY);
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export { API_KEY_STORAGE_KEY, JWT_STORAGE_KEY };
export default client;
