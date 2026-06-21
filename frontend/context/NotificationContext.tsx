"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  ReactNode,
} from "react";
import { api } from "../lib/api";
import { useAuth } from "./AuthContext";
import { useToast } from "./ToastContext";

export interface Notification {
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

interface NotificationContextType {
  notifications: Notification[];
  unreadCount: number;
  isLoading: boolean;
  fetchNotifications: () => Promise<void>;
  markAsRead: (notificationId: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  deleteNotification: (notificationId: string) => Promise<void>;
}

const NotificationContext = createContext<NotificationContextType | null>(null);

const getBaseUrl = (): string => {
  if (typeof window !== "undefined") {
    // Client-side, use environment variable
    return (window as any).NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  }
  // Server-side fallback
  return "http://localhost:8000/api/v1";
};

const getWsUrl = (): string => {
  const apiUrl = getBaseUrl();
  return apiUrl.replace(/^http/, "ws") + "/notifications/ws";
};

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { token, isAuthenticated } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const { addToast } = useToast();

  const fetchNotifications = useCallback(async () => {
    if (!token || !isAuthenticated) return;

    setIsLoading(true);
    try {
      const [notificationsData, unreadCountData] = await Promise.all([
        api.notifications.get(token),
        api.notifications.getUnreadCount(token),
      ]);
      setNotifications(notificationsData);
      setUnreadCount(unreadCountData.unread_count);
    } catch (error) {
      console.error("Failed to fetch notifications:", error);
    } finally {
      setIsLoading(false);
    }
  }, [token, isAuthenticated]);

  const markAsRead = useCallback(
    async (notificationId: string) => {
      if (!token) return;

      try {
        await api.notifications.markAsRead(token, notificationId);
        // Update local state
        setNotifications((prev: Notification[]) =>
          prev.map((n: Notification) =>
            n.id === notificationId ? { ...n, read: true } : n
          )
        );
        setUnreadCount((prev: number) => Math.max(0, prev - 1));
      } catch (error) {
        console.error("Failed to mark notification as read:", error);
      }
    },
    [token]
  );

  const markAllAsRead = useCallback(async () => {
    if (!token) return;

    try {
      await api.notifications.markAllAsRead(token);
      // Update local state
      setNotifications((prev: Notification[]) =>
        prev.map((n: Notification) => ({ ...n, read: true }))
      );
      setUnreadCount(0);
    } catch (error) {
      console.error("Failed to mark all notifications as read:", error);
    }
  }, [token]);

  const deleteNotification = useCallback(
    async (notificationId: string) => {
      if (!token) return;

      try {
        await api.notifications.delete(token, notificationId);
        // Update local state
        setNotifications((prev: Notification[]) =>
          prev.filter((n: Notification) => n.id !== notificationId)
        );
        // Recalculate unread count
        setUnreadCount((prev: number) => {
          const deletedNotification = notifications.find(
            (n: Notification) => n.id === notificationId
          );
          return deletedNotification && !deletedNotification.read
            ? Math.max(0, prev - 1)
            : prev;
        });
      } catch (error) {
        console.error("Failed to delete notification:", error);
      }
    },
    [token, notifications]
  );

  const connectWebSocket = useCallback(() => {
    if (!token || !isAuthenticated) return;

    if (wsRef.current) {
      wsRef.current.close();
    }

    const wsUrl = `${getWsUrl()}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected");
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "notification" && data.data) {
          const newNotification = data.data as Notification;
          setNotifications((prev: Notification[]) => [
            newNotification,
            ...prev,
          ]);
          setUnreadCount((prev: number) => prev + 1);
          addToast(newNotification.message, "info");
        }
      } catch (error) {
        console.error("Failed to parse WebSocket message:", error);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    ws.onclose = (event) => {
      console.log("WebSocket closed, reconnecting in 5s...", event);
      if (isAuthenticated) {
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connectWebSocket();
        }, 5000);
      }
    };
  }, [token, isAuthenticated, addToast]);

  useEffect(() => {
    if (!isAuthenticated || !token) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      setNotifications([]);
      setUnreadCount(0);
      return;
    }

    fetchNotifications();
    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [isAuthenticated, token, fetchNotifications, connectWebSocket]);

  const value: NotificationContextType = {
    notifications,
    unreadCount,
    isLoading,
    fetchNotifications,
    markAsRead,
    markAllAsRead,
    deleteNotification,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications(): NotificationContextType {
  const ctx = useContext(NotificationContext);
  if (!ctx)
    throw new Error(
      "useNotifications must be used within a NotificationProvider"
    );
  return ctx;
}
