import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "";

export const api = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

const ACCESS = "ci_access_token";
const REFRESH = "ci_refresh_token";

export function getStoredAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS);
}

export function getStoredRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH);
}

export function setTokens(access: string, refresh: string): void {
  sessionStorage.setItem(ACCESS, access);
  sessionStorage.setItem(REFRESH, refresh);
}

export function clearTokens(): void {
  sessionStorage.removeItem(ACCESS);
  sessionStorage.removeItem(REFRESH);
}

let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const rt = getStoredRefreshToken();
  if (!rt) throw new Error("No refresh token");
  const { data } = await axios.post<{ access_token: string; token_type: string }>(
    `${baseURL}/api/v1/auth/refresh`,
    { refresh_token: rt },
  );
  const access = data.access_token;
  sessionStorage.setItem(ACCESS, access);
  return access;
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getStoredAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config;
    if (!original || original.url?.includes("/auth/refresh")) {
      return Promise.reject(error);
    }
    if (error.response?.status !== 401) {
      return Promise.reject(error);
    }
    if ((original as InternalAxiosRequestConfig & { _retry?: boolean })._retry) {
      clearTokens();
      return Promise.reject(error);
    }
    (original as InternalAxiosRequestConfig & { _retry?: boolean })._retry = true;
    try {
      if (!refreshPromise) {
        refreshPromise = refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }
      const newAccess = await refreshPromise;
      original.headers.Authorization = `Bearer ${newAccess}`;
      return api(original);
    } catch {
      clearTokens();
      return Promise.reject(error);
    }
  },
);
