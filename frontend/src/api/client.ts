/**
 * Sentra-X API Client
 * Configures JWT Bearer token injection and handles typed HTTP errors (401, 403, 422).
 */

export class ApiError extends Error {
  status: number;
  data?: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

const RAW_API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').trim();
// Strip trailing slash to guarantee predictable URL concatenation
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, '');

export function isLiveBackendConfigured(): boolean {
  return Boolean(API_BASE_URL && API_BASE_URL.length > 0);
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('sentrax_jwt_token');

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json, text/csv, */*',
    ...(options.headers as Record<string, string>),
  };

  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${API_BASE_URL}${cleanEndpoint}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      try {
        errorData = await response.text();
      } catch {
        errorData = null;
      }
    }

    let message = `HTTP ${response.status} Error`;

    if (typeof errorData === 'object' && errorData !== null && 'detail' in errorData) {
      const detail = (errorData as { detail: unknown }).detail;
      // Handle FastAPI Pydantic validation error array
      if (Array.isArray(detail)) {
        message = detail
          .map((item: unknown) => {
            if (typeof item === 'object' && item !== null && 'msg' in item) {
              const errObj = item as { loc?: unknown[]; msg: string };
              const loc = Array.isArray(errObj.loc)
                ? errObj.loc.filter((part) => part !== 'body').join('.')
                : '';
              return loc ? `${loc}: ${errObj.msg}` : errObj.msg;
            }
            return typeof item === 'string' ? item : JSON.stringify(item);
          })
          .join('; ');
      } else if (typeof detail === 'string') {
        message = detail;
      } else {
        message = JSON.stringify(detail);
      }
    } else if (response.status === 401) {
      message = 'HTTP 401 Unauthorized: Invalid credentials or session expired.';
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('sentrax:unauthorized'));
      }
    } else if (response.status === 403) {
      message = 'HTTP 403 Forbidden: Insufficient role permissions for this resource.';
    } else if (response.status === 422) {
      message = 'HTTP 422 Unprocessable Entity: Decision rationale must be at least 10 characters or payload validation failed.';
    } else if (response.status === 500) {
      message = 'HTTP 500 Internal Server Error: An unexpected error occurred on the Sentra-X backend server.';
    } else if (response.statusText) {
      message = `HTTP ${response.status}: ${response.statusText}`;
    }

    throw new ApiError(response.status, message, errorData);
  }

  if (response.status === 204) {
    return undefined as unknown as T;
  }

  const contentType = response.headers.get('Content-Type') || '';
  if (contentType.includes('text/csv') || contentType.includes('text/plain')) {
    return (await response.text()) as unknown as T;
  }

  return (await response.json()) as T;
}

