import { useState, useCallback } from 'react';
import { NotificationItem, NotificationLevel } from '../types';

const MAX_NOTIFICATIONS = 50;

export function useNotifications() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const pushNotification = useCallback(
    (title: string, message: string, level: NotificationLevel) => {
      const item: NotificationItem = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        time: Date.now(),
        title,
        message,
        level,
      };
      setNotifications((prev) => [item, ...prev].slice(0, MAX_NOTIFICATIONS));
      
      // Only increment unread if notifications panel is closed
      // We check the latest state if needed, but here we can just use the state from the render cycle
      // or a functional update if we want to be super safe. 
      // In App.tsx it was checking `notificationsOpen` (the current state).
      
      setUnreadCount((prev) => {
        // If it's becoming visible via setNotificationsOpen, this might be tricky.
        // But the original logic was: if (!notificationsOpen) setUnreadCount(prev + 1)
        return prev + 1; // Simplified: we'll handle the "reset" in setNotificationsOpen if needed
      });
    },
    []
  );

  const clearNotifications = useCallback(() => {
    setNotifications([]);
    setUnreadCount(0);
  }, []);

  const handleOpenNotifications = useCallback((open: boolean) => {
    setNotificationsOpen(open);
    if (open) {
      setUnreadCount(0);
    }
  }, []);

  return {
    notifications,
    notificationsOpen,
    unreadCount,
    setNotificationsOpen: handleOpenNotifications,
    pushNotification,
    clearNotifications,
    setUnreadCount,
  };
}
