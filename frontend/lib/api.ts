/**
 * Frontend API client for the StellArts backend.
 * Base URL: NEXT_PUBLIC_API_URL (e.g. http://localhost:8000/api/v1)
 */

const getBaseUrl = (): string =>
  typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL
    : "http://localhost:8000/api/v1";

async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, ...init } = options;
  const url = `${getBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(url, { ...init, headers });
  const text = await res.text();
  if (!res.ok) {
    let message = res.statusText;
    try {
      const json = JSON.parse(text);
      message = json.detail ?? (typeof json.detail === "string" ? json.detail : message);
      if (Array.isArray(json.detail))
        message = json.detail.map((d: { msg?: string }) => d.msg ?? "").join("; ") || message;
    } catch {
      if (text) message = text;
    }
    throw new Error(message);
  }
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

// --- Types (aligned with backend schemas) ---

export interface UserOut {
  id: number;
  email: string;
  role: string;
  full_name: string | null;
  phone: string | null;
  username: string | null;
}

export interface ArtisanItem {
  id: number;
  business_name?: string | null;
  description?: string | null;
  specialties?: string | string[] | null;
  experience_years?: number | null;
  hourly_rate?: number | null;
  location?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  is_verified?: boolean;
  is_available?: boolean;
  rating?: number | null;
  total_reviews?: number;
  distance_km?: number | null;
}

export interface PortfolioItem {
  id: number;
  title?: string | null;
  image: string;
}

export interface ArtisanProfileResponse {
  id: number;
  name: string | null;
  avatar?: string | null;
  specialty?: string | null;
  rate?: number | null;
  bio?: string | null;
  portfolio?: PortfolioItem[];
  average_rating?: number | null;
  location?: string | null;
}

export interface BookingCreate {
  artisan_id: number;
  service: string;
  date: string;
  estimated_cost: number;
  estimated_hours?: number | null;
  location?: string | null;
  notes?: string | null;
}

export interface BookingResponse {
  id: string;
  client_id: number;
  artisan_id: number;
  service: string;
  date: string | null;
  estimated_cost: number | null;
  estimated_hours: number | null;
  status: string;
  location: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type?: string;
}

interface PaginatedArtisansResponse {
  items: ArtisanItem[];
  total: number;
  page: number;
  page_size: number;
}

// --- API object ---

export const api = {
  auth: {
    login: (body: { email: string; password: string }) =>
      request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
    register: (body: {
      email: string;
      password: string;
      role: "client" | "artisan";
      full_name?: string | null;
      phone?: string | null;
    }) =>
      request<{ id: number; role: string }>("/auth/register", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },
  users: {
    me: (token: string) =>
      request<UserOut>("/users/me", { method: "GET", token }),
  },
  artisans: {
    nearby: (
      lat: number,
      lon: number,
      opts: { page?: number; page_size?: number } = {}
    ) => {
      const params = new URLSearchParams({
        lat: String(lat),
        lon: String(lon),
        page: String(opts.page ?? 1),
        page_size: String(opts.page_size ?? 10),
      });
      return request<PaginatedArtisansResponse>(`/artisans/nearby?${params}`);
    },
    getProfile: (artisanId: number) =>
      request<ArtisanProfileResponse>(`/artisans/${artisanId}/profile`),
  },
  bookings: {
    myBookings: (token: string) =>
      request<BookingResponse[]>("/bookings/my-bookings", { method: "GET", token }),
    create: (body: BookingCreate, token: string) =>
      request<BookingResponse>("/bookings/create", {
        method: "POST",
        body: JSON.stringify(body),
        token,
      }),
  },
};
