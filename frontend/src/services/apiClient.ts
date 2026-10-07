/**
 * Cliente HTTP centralizado do SGI.
 *
 * Responsabilidades:
 * - Base URL da API
 * - Bearer token
 * - serialização JSON
 * - tratamento padronizado de erros HTTP
 * - respostas 204
 */

const PUBLIC_API_BASE_URL =
  (import.meta.env["VITE_API_URL"] as string | undefined)?.replace(/\/+$/, "") ||
  "/api";

const INTERNAL_API_BASE_URL =
  typeof process !== "undefined"
    ? process.env["API_INTERNAL_URL"]?.replace(/\/+$/, "")
    : undefined;

export const API_BASE_URL: string = import.meta.env.SSR
  ? INTERNAL_API_BASE_URL || "http://backend:8000"
  : PUBLIC_API_BASE_URL;

const ACCESS_TOKEN_KEY = "sgi.access_token";

const REQUEST_TIMEOUT_MS = 20_000;

export interface ApiErrorPayload {
  detail?: unknown;
  mensagem?: unknown;
  message?: unknown;
  [key: string]: unknown;
}

export class ApiError extends Error {
  status: number;
  payload?: unknown;

  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export interface ApiRequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  headers?: Record<string, string>;
  authenticated?: boolean;
  timeoutMs?: number;
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
}

function extractErrorMessage(payload: unknown, status: number): string {
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }

  if (payload && typeof payload === "object") {
    const data = payload as ApiErrorPayload;

    if (typeof data.detail === "string" && data.detail.trim()) {
      return data.detail;
    }

    if (typeof data.mensagem === "string" && data.mensagem.trim()) {
      return data.mensagem;
    }

    if (typeof data.message === "string" && data.message.trim()) {
      return data.message;
    }

    if (Array.isArray(data.detail)) {
      const first = data.detail[0];

      if (
        first &&
        typeof first === "object" &&
        "msg" in first &&
        typeof (first as { msg?: unknown }).msg === "string"
      ) {
        return String((first as { msg: string }).msg);
      }
    }
  }

  switch (status) {
    case 400:
      return "A operação não pôde ser concluída.";
    case 401:
      return "Sessão inválida ou expirada.";
    case 403:
      return "Você não possui permissão para executar esta operação.";
    case 404:
      return "Registro não encontrado.";
    case 409:
      return "A operação entrou em conflito com o estado atual.";
    case 422:
      return "Os dados informados são inválidos.";
    case 500:
      return "O SGI encontrou uma falha interna.";
    default:
      return `Falha na comunicação com o SGI (HTTP ${status}).`;
  }
}

async function parseResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return undefined;
  }

  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return undefined;
    }
  }

  try {
    const text = await response.text();
    return text || undefined;
  } catch {
    return undefined;
  }
}

export async function apiRequest<T>(
  path: string,
  {
    method = "GET",
    body,
    signal,
    headers = {},
    authenticated = true,
    timeoutMs = REQUEST_TIMEOUT_MS,
  }: ApiRequestOptions = {},
): Promise<T> {
  const token = authenticated ? getAccessToken() : null;

  const requestHeaders: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };

  if (body !== undefined) {
    requestHeaders["Content-Type"] = "application/json";
  }

  if (token) {
    requestHeaders["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;

  const requestController = new AbortController();
  let timeoutEsgotado = false;

  const cancelarPorSinalExterno = () => {
    requestController.abort(signal?.reason);
  };

  if (signal?.aborted) {
    cancelarPorSinalExterno();
  } else {
    signal?.addEventListener(
      "abort",
      cancelarPorSinalExterno,
      { once: true },
    );
  }

  const timeoutId =
    timeoutMs > 0
      ? globalThis.setTimeout(() => {
          timeoutEsgotado = true;
          requestController.abort();
        }, timeoutMs)
      : null;

  try {
    const requestInit: RequestInit = {
      method,
      headers: requestHeaders,
      signal: requestController.signal,
    };

    if (body !== undefined) {
      requestInit.body = JSON.stringify(body);
    }

    response = await fetch(
      `${API_BASE_URL}${path}`,
      requestInit,
    );
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      if (timeoutEsgotado) {
        throw new ApiError(
          `A solicitação demorou mais de ${Math.ceil(timeoutMs / 1000)} segundos. Tente novamente.`,
          408,
          error,
        );
      }

      throw error;
    }

    throw new ApiError(
      "Não foi possível conectar ao backend do SGI.",
      0,
      error,
    );
  } finally {
    if (timeoutId !== null) {
      globalThis.clearTimeout(timeoutId);
    }

    signal?.removeEventListener(
      "abort",
      cancelarPorSinalExterno,
    );
  }

  const payload = await parseResponseBody(response);

  if (!response.ok) {
    if (response.status === 401) {
      clearAccessToken();
    }

    throw new ApiError(
      extractErrorMessage(payload, response.status),
      response.status,
      payload,
    );
  }

  return payload as T;
}

