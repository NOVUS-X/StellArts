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
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, ...init } = options;
  const url = `${getBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
  const headers: HeadersInit = {
    ...(init.headers as Record<string, string>),
  };
  if (!(init.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(url, { ...init, headers });
  const text = await res.text();

  if (!res.ok) {
    let message = res.statusText;
    try {
      const json = JSON.parse(text);
      message =
        json.detail ??
        (typeof json.detail === "string" ? json.detail : message);
      if (Array.isArray(json.detail)) {
        message =
          json.detail.map((d: { msg?: string }) => d.msg ?? "").join("; ") ||
          message;
      }
    } catch {
      if (text) message = text;
    }
    throw new Error(message);
  }

  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

// --- Types ---

export interface UserOut {
  id: number;
  email: string;
  role: string;
  full_name: string | null;
  phone: string | null;
  username: string | null;
  avatar: string | null;
}

export interface ArtisanProfileUpdate {
  business_name?: string | null;
  description?: string | null;
  specialties?: string[] | null;
  experience_years?: number | null;
  hourly_rate?: number | null;
  location?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  is_available?: boolean | null;
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
  artisan_name?: string;
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

export interface NotificationItem {
  id: string;
  user_id: number;
  type: string;
  title: string;
  message: string;
  read: boolean;
  reference_id: string | null;
  created_at: string;
  updated_at: string;
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

// --- API ---

export const api = {
  auth: {
    login: (body: { email: string; password: string }) =>
      request<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
      }),
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
    updateMe: (body: Partial<UserOut>, token: string) =>
      request<UserOut>("/users/me", {
        method: "PUT",
        body: JSON.stringify(body),
        token,
      }),
    uploadAvatar: (file: File, token: string) => {
      const formData = new FormData();
      formData.append("file", file);
      return request<UserOut>("/users/me/avatar", {
        method: "POST",
        body: formData,
        token,
      });
    },
  },

  artisans: {
    me: (token: string) =>
      request<ArtisanItem>("/artisans/me", { method: "GET", token }),

    nearby: (
      lat: number,
      lon: number,
      opts: {
        page?: number;
        page_size?: number;
        skills?: string[];
        skill?: string;
        min_rating?: number;
        min_experience?: number;
        min_rate?: number;
        max_rate?: number;
        is_available?: boolean;
      } = {},
    ) => {
      const params = new URLSearchParams({
        lat: String(lat),
        lon: String(lon),
        page: String(opts.page ?? 1),
        page_size: String(opts.page_size ?? 10),
      });

      if (opts.skills && opts.skills.length > 0) {
        opts.skills.forEach((skill) => params.append("skills", skill));
      }

      if (opts.skill) {
        params.append("skill", opts.skill);
      }

      if (opts.min_rating !== undefined && opts.min_rating > 0) {
        params.append("min_rating", String(opts.min_rating));
      }

      if (opts.min_experience !== undefined && opts.min_experience > 0) {
        params.append("min_experience", String(opts.min_experience));
      }

      if (opts.min_rate !== undefined && opts.min_rate > 0) {
        params.append("min_rate", String(opts.min_rate));
      }

      if (opts.max_rate !== undefined && opts.max_rate > 0) {
        params.append("max_rate", String(opts.max_rate));
      }

      if (opts.is_available !== undefined) {
        params.append("is_available", String(opts.is_available));
      }

      return request<PaginatedArtisansResponse>(
        `/artisans/nearby?${params}`,
      );
    },

    getProfile: (artisanId: number) =>
      request<ArtisanProfileResponse>(
        `/artisans/${artisanId}/profile`,
      ),

    updateProfile: (body: ArtisanProfileUpdate, token: string) =>
      request<ArtisanItem>("/artisans/profile", {
        method: "PUT",
        body: JSON.stringify(body),
        token,
      }),
  },

  bookings: {
    myBookings: (token: string) =>
      request<BookingResponse[]>("/bookings/my-bookings", {
        method: "GET",
        token,
      }),
    create: (body: BookingCreate, token: string) =>
      request<BookingResponse>("/bookings/create", {
        method: "POST",
        body: JSON.stringify(body),
        token,
      }),
  },

  notifications: {
    get: (token: string, skip = 0, limit = 50) =>
      request<NotificationItem[]>(
        `/notifications/?skip=${skip}&limit=${limit}`,
        { method: "GET", token },
      ),

    getUnreadCount: (token: string) =>
      request<{ unread_count: number }>(
        "/notifications/unread-count",
        { method: "GET", token },
      ),

    markAsRead: (token: string, id: string) =>
      request<NotificationItem>(`/notifications/${id}/read`, {
        method: "PUT",
        token,
      }),

    markAllAsRead: (token: string) =>
      request<{ message: string }>(
        "/notifications/mark-all-read",
        { method: "PUT", token },
      ),

    delete: (token: string, id: string) =>
      request<{ message: string }>(`/notifications/${id}`, {
        method: "DELETE",
        token,
      }),
  },
};