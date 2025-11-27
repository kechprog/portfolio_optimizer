/**
 * HTTP API service for communicating with the backend.
 * Handles dashboard data fetching with Auth0 token authentication.
 */

import { Allocator, DateRange } from '../types';

// API response types
export interface DashboardSettings {
  fit_start_date: string | null;
  fit_end_date: string | null;
  test_end_date: string | null;
  include_dividends: boolean;
}

export interface DashboardResponse {
  allocators: Array<{
    id: string;
    type: string;
    config: Record<string, unknown>;
    enabled: boolean;
  }>;
  settings: DashboardSettings;
}

/**
 * Get the API base URL based on environment.
 * In development, connects to backend on port 8000.
 * In production, uses same host as frontend.
 */
const getApiBaseUrl = (): string => {
  if (typeof window === 'undefined') return 'http://localhost:8000';

  // Check for explicit API URL (useful for development)
  const envApiUrl = import.meta.env.VITE_API_URL;
  if (envApiUrl) return envApiUrl;

  // In development (Vite dev server), connect to backend on port 8000
  if (import.meta.env.DEV) {
    const protocol = window.location.protocol;
    return `${protocol}//${window.location.hostname}:8000`;
  }

  // In production, use same host (assumes backend serves frontend)
  return '';
};

const API_BASE_URL = getApiBaseUrl();

/**
 * Fetch dashboard data (allocators and settings) for the current user.
 *
 * @param token - Auth0 access token for authentication
 * @returns Dashboard data with allocators and settings
 * @throws Error if the request fails
 */
export async function fetchDashboard(token: string): Promise<DashboardResponse> {
  const response = await fetch(`${API_BASE_URL}/api/dashboard`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Authentication failed. Please log in again.');
    }
    if (response.status === 503) {
      throw new Error('Authentication not configured on server.');
    }
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch dashboard: ${response.status}`);
  }

  return response.json();
}

/**
 * Transform API allocator data to frontend Allocator type.
 */
export function transformAllocator(apiAllocator: DashboardResponse['allocators'][0]): Allocator {
  return {
    id: apiAllocator.id,
    type: apiAllocator.type as Allocator['type'],
    config: apiAllocator.config as unknown as Allocator['config'],
    enabled: apiAllocator.enabled,
  } as Allocator;
}

/**
 * Transform API settings to frontend DateRange type.
 */
export function transformSettings(settings: DashboardSettings): {
  dateRange: DateRange | null;
  includeDividends: boolean;
} {
  const dateRange: DateRange | null = (settings.fit_start_date && settings.fit_end_date && settings.test_end_date)
    ? {
        fit_start_date: settings.fit_start_date,
        fit_end_date: settings.fit_end_date,
        test_end_date: settings.test_end_date,
      }
    : null;

  return {
    dateRange,
    includeDividends: settings.include_dividends,
  };
}
