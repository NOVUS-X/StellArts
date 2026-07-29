"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useNotifications, Notification } from "../../context/NotificationContext";
import { useAuth } from "../../context/AuthContext";

export default function NotificationBell() {
  const {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    deleteNotification,
  } = useNotifications();
  const { isAuthenticated } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!isAuthenticated) {
    return null;
  }

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case "booking_confirmed":
      case "booking_created":
        return "✓";
      case "booking_started":
        return "🔧";
      case "booking_completed":
        return "✅";
      case "booking_cancelled":
        return "❌";
      case "bid_received":
        return "💬";
      case "payment_released":
        return "💰";
      case "payment_refunded":
        return "↩️";
      default:
        return "🔔";
    }
  };

  const getNotificationColor = (type: string) => {
    switch (type) {
      case "booking_confirmed":
      case "booking_completed":
      case "booking_created":
        return "text-green-600 dark:text-green-400";
      case "booking_started":
      case "bid_received":
        return "text-blue-600 dark:text-blue-400";
      case "booking_cancelled":
        return "text-red-600 dark:text-red-400";
      case "payment_released":
      case "payment_refunded":
        return "text-amber-600 dark:text-amber-400";
      default:
        return "text-gray-600 dark:text-gray-400";
    }
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return "";
    const date = new Date(dateString);
    const now = new Date();
    const diffInMs = now.getTime() - date.getTime();
    const diffInMinutes = Math.floor(diffInMs / 60000);
    const diffInHours = Math.floor(diffInMinutes / 60);
    const diffInDays = Math.floor(diffInHours / 24);

    if (diffInMinutes < 1) return "Just now";
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    if (diffInHours < 24) return `${diffInHours}h ago`;
    if (diffInDays < 7) return `${diffInDays}d ago`;
    return date.toLocaleDateString();
  };

  const handleNotificationClick = async (notification: Notification) => {
    if (!notification.read && !notification.is_read) {
      await markAsRead(notification.id);
    }

    setIsOpen(false);

    // Redirect to relevant section/page
    if (notification.type.startsWith("payment")) {
      router.push("/analytics");
    } else if (notification.type.startsWith("booking") || notification.type.startsWith("bid")) {
      router.push("/dashboard");
    } else {
      router.push("/dashboard");
    }
  };

  const handleMarkAllRead = async () => {
    await markAllAsRead();
  };

  const handleDeleteNotification = async (
    e: React.MouseEvent,
    notificationId: string
  ) => {
    e.stopPropagation();
    await deleteNotification(notificationId);
  };

  const recentNotifications = notifications.slice(0, 10);

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Icon */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-muted-foreground hover:text-foreground transition-colors rounded-full hover:bg-accent"
        aria-label="Notifications"
      >
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center animate-pulse">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-96 bg-background rounded-lg shadow-xl border border-border max-h-96 overflow-hidden z-50">
          {/* Header */}
          <div className="px-4 py-3 border-b border-border bg-muted/50 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground">
              Notifications
            </h3>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
              >
                Mark all as read
              </button>
            )}
          </div>

          {/* Notifications List */}
          <div className="overflow-y-auto max-h-80 divide-y divide-border">
            {recentNotifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-muted-foreground">
                <svg
                  className="mx-auto h-12 w-12 text-muted-foreground/50 mb-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                  />
                </svg>
                <p className="text-sm">No notifications yet</p>
              </div>
            ) : (
              recentNotifications.map((notification) => {
                const isUnread = !notification.read && !notification.is_read;
                return (
                  <div
                    key={notification.id}
                    onClick={() => handleNotificationClick(notification)}
                    className={`px-4 py-3 cursor-pointer transition-colors hover:bg-accent/80 flex items-start gap-3 ${
                      isUnread
                        ? "bg-blue-50/70 dark:bg-blue-950/30 font-medium"
                        : "bg-background"
                    }`}
                  >
                    <span
                      className={`text-lg mt-0.5 ${getNotificationColor(
                        notification.type
                      )}`}
                    >
                      {getNotificationIcon(notification.type)}
                    </span>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p
                          className={`text-sm text-foreground ${
                            isUnread ? "font-semibold" : "font-normal"
                          }`}
                        >
                          {notification.title}
                        </p>
                        {isUnread && (
                          <span className="w-2 h-2 rounded-full bg-blue-600 dark:bg-blue-400 inline-block ml-1" />
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {notification.message}
                      </p>
                      <p className="text-[10px] text-muted-foreground/70 mt-1">
                        {formatDate(notification.created_at)}
                      </p>
                    </div>

                    <button
                      onClick={(e) =>
                        handleDeleteNotification(e, notification.id)
                      }
                      className="text-muted-foreground hover:text-destructive transition-colors p-1"
                      aria-label="Delete notification"
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
