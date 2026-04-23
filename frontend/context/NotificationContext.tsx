"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { api } from "../lib/api";
import { useAuth } from "./AuthContext";

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

const POLLING_INTERVAL = 30000; // 30 seconds

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { token, isAuthenticated } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

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
        setNotifications((prev) =>
          prev.map((n) => (n.id === notificationId ? { ...n, read: true } : n)),
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      } catch (error) {
        console.error("Failed to mark notification as read:", error);
      }
    },
    [token],
  );

  const markAllAsRead = useCallback(async () => {
    if (!token) return;

    try {
      await api.notifications.markAllAsRead(token);
      // Update local state
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
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
        // Recalculate unread count
        setUnreadCount((prev) => {
          const deletedNotification = notifications.find(
            (n) => n.id === notificationId,
          );
          return deletedNotification && !deletedNotification.read
            ? Math.max(0, prev - 1)
            : prev;
        });
      } catch (error) {
        console.error("Failed to delete notification:", error);
      }
    },
    [token, notifications],
  );

  // Poll for new notifications
  useEffect(() => {
    if (!isAuthenticated || !token) {
      setNotifications([]);
      setUnreadCount(0);
      return;
    }

    fetchNotifications();

    const interval = setInterval(fetchNotifications, POLLING_INTERVAL);
    return () => clearInterval(interval);
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
      "useNotifications must be used within a NotificationProvider",
    );
  return ctx;
}
