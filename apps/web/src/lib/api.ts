"use client";

import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? decodeURIComponent(match[2]) : null;
}

api.interceptors.request.use((config) => {
  const method = (config.method || "get").toLowerCase();
  if (!["get", "head", "options"].includes(method)) {
    const csrf = getCookie("topec_legal_csrf");
    if (csrf) {
      config.headers = config.headers || {};
      config.headers["X-CSRF-Token"] = csrf;
    }
  }
  return config;
});

export interface ApiErrorShape {
  detail?: string;
}

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ApiErrorShape | undefined;
    return data?.detail || error.message || "요청 처리 중 오류가 발생했습니다.";
  }
  return "요청 처리 중 알 수 없는 오류가 발생했습니다.";
}
