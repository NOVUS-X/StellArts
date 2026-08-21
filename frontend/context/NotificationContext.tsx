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
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "./AuthContext";

export interface Notification {
  id: string;
  user_id: number;
  type: string;
  title: string;
  message: string;
  read: boolean;
  is_read?: boolean;
  reference_id: string | null;
  created_at: string;
  updated_at?: string;
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

const POLLING_INTERVAL = 30000; // Fallback polling interval 30 seconds

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { token, isAuthenticated } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);

  const fetchNotifications = useCallback(async () => {
    if (!token || !isAuthenticated) return;

    setIsLoading(true);
    try {
      const [notificationsData, unreadCountData] = await Promise.all([
        api.notifications.get(token),
        api.notifications.getUnreadCount(token),
      ]);
      setNotifications(
        notificationsData.map((n) => ({
          ...n,
          read: n.read ?? n.is_read ?? false,
        }))
      );
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
        setNotifications((prev) =>
          prev.map((n) =>
            n.id === notificationId ? { ...n, read: true, is_read: true } : n
          )
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
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
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, read: true, is_read: true }))
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
        setNotifications((prev) => prev.filter((n) => n.id !== notificationId));
        setUnreadCount((prev) => {
          const deletedNotification = notifications.find(
            (n) => n.id === notificationId
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

  // WebSocket Connection Handler
  useEffect(() => {
    if (!isAuthenticated || !token) {
      setNotifications([]);
      setUnreadCount(0);

      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      return;
    }

    // Initial fetch of notifications
    fetchNotifications();

    const connectWebSocket = () => {
      try {
        const baseUrl =
          process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
        const wsProtocol = baseUrl.startsWith("https") ? "wss" : "ws";
        const hostAndPath = baseUrl.replace(/^https?:\/\//, "");
        const wsUrl = `${wsProtocol}://${hostAndPath}/notifications/stream?token=${encodeURIComponent(
          token
        )}`;

        const ws = new WebSocket(wsUrl);
        socketRef.current = ws;

        ws.onopen = () => {
          console.log("WebSocket connected for real-time notifications");
          reconnectAttemptsRef.current = 0;
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data && data.id) {
              const newNotification: Notification = {
                id: data.id,
                user_id: data.user_id,
                type: data.type,
                title: data.title || "New Notification",
                message: data.message || "",
                read: data.read ?? data.is_read ?? false,
                is_read: data.is_read ?? data.read ?? false,
                reference_id: data.reference_id || null,
                created_at: data.created_at || new Date().toISOString(),
                updated_at: data.updated_at,
              };

              setNotifications((prev) => [
                newNotification,
                ...prev.filter((n) => n.id !== newNotification.id),
              ]);
              setUnreadCount((prev) => prev + 1);

              // Trigger dynamic toast popup
              toast.info(newNotification.title, {
                description: newNotification.message,
              });
            }
          } catch (err) {
            console.error("Failed to parse WebSocket notification message:", err);
          }
        };

        ws.onerror = (err) => {
          console.warn("WebSocket error encountered:", err);
        };

        ws.onclose = () => {
          console.log("WebSocket closed, attempting reconnect...");
          socketRef.current = null;

          // Reconnect with exponential backoff (2s, 4s, 8s, max 30s)
          const attempts = reconnectAttemptsRef.current;
          const delay = Math.min(1000 * Math.pow(2, attempts), 30000);
          reconnectAttemptsRef.current += 1;

          reconnectTimeoutRef.current = setTimeout(() => {
            if (isAuthenticated && token) {
              connectWebSocket();
            }
          }, delay);
        };
      } catch (err) {
        console.error("Failed to establish WebSocket connection:", err);
      }
    };

    connectWebSocket();

    // Fallback polling interval
    const interval = setInterval(fetchNotifications, POLLING_INTERVAL);

    return () => {
      clearInterval(interval);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [isAuthenticated, token, fetchNotifications]);

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
