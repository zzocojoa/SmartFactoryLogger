import { useReducer, useCallback } from 'react';
import { NotificationItem, NotificationLevel, NotificationPushOptions } from '../types';

const MAX_NOTIFICATIONS = 50;

interface NotificationState {
  notifications: NotificationItem[];
  notificationsOpen: boolean;
  unreadCount: number;
}

export interface UseNotificationsResult {
  notifications: NotificationItem[];
  notificationsOpen: boolean;
  unreadCount: number;
  setNotificationsOpen: (open: boolean) => void;
  pushNotification: (
    title: string,
    message: string,
    level: NotificationLevel,
    options?: NotificationPushOptions
  ) => void;
  clearNotifications: () => void;
  setUnreadCount: (count: number) => void;
}

type NotificationAction =
  | { type: 'push'; item: NotificationItem }
  | { type: 'clear' }
  | { type: 'setOpen'; open: boolean }
  | { type: 'setUnreadCount'; count: number };

const createNotificationId = (): string => {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
};

const isSameActiveNotification = (
  current: NotificationItem,
  next: NotificationItem
): boolean => {
  return (
    current.title === next.title &&
    current.message === next.message &&
    current.level === next.level &&
    current.detail === next.detail
  );
};

const replaceActiveNotificationGroup = (
  notifications: NotificationItem[],
  item: NotificationItem
): NotificationItem[] => {
  const withoutActiveGroup = notifications.filter((current) => {
    return current.groupKey !== item.groupKey || current.lifecycle !== 'active';
  });

  return [item, ...withoutActiveGroup].slice(0, MAX_NOTIFICATIONS);
};

const pushNotificationItem = (
  notifications: NotificationItem[],
  item: NotificationItem
): NotificationItem[] | null => {
  if (item.groupKey && item.lifecycle === 'active') {
    const activeItem = notifications.find((current) => {
      return current.groupKey === item.groupKey && current.lifecycle === 'active';
    });

    if (activeItem && isSameActiveNotification(activeItem, item)) {
      return null;
    }

    const withoutActiveGroup = notifications.filter((current) => {
      return current.groupKey !== item.groupKey || current.lifecycle !== 'active';
    });
    return [item, ...withoutActiveGroup].slice(0, MAX_NOTIFICATIONS);
  }

  if (item.groupKey && item.lifecycle === 'resolved') {
    return replaceActiveNotificationGroup(notifications, item);
  }

  return [item, ...notifications].slice(0, MAX_NOTIFICATIONS);
};

const notificationReducer = (
  state: NotificationState,
  action: NotificationAction
): NotificationState => {
  if (action.type === 'push') {
    const notifications = pushNotificationItem(state.notifications, action.item);
    if (notifications === null) {
      return state;
    }

    return {
      ...state,
      notifications,
      unreadCount: state.notificationsOpen ? state.unreadCount : state.unreadCount + 1,
    };
  }

  if (action.type === 'clear') {
    return {
      ...state,
      notifications: [],
      unreadCount: 0,
    };
  }

  if (action.type === 'setOpen') {
    return {
      ...state,
      notificationsOpen: action.open,
      unreadCount: action.open ? 0 : state.unreadCount,
    };
  }

  return {
    ...state,
    unreadCount: action.count,
  };
};

export function useNotifications(): UseNotificationsResult {
  const [state, dispatch] = useReducer(notificationReducer, {
    notifications: [],
    notificationsOpen: false,
    unreadCount: 0,
  });

  const pushNotification = useCallback(
    (
      title: string,
      message: string,
      level: NotificationLevel,
      options?: NotificationPushOptions
    ): void => {
      const item: NotificationItem = {
        id: createNotificationId(),
        time: Date.now(),
        title,
        message,
        level,
        groupKey: options?.groupKey,
        lifecycle: options?.lifecycle,
        detail: options?.detail,
      };
      dispatch({ type: 'push', item });
    },
    []
  );

  const clearNotifications = useCallback(() => {
    dispatch({ type: 'clear' });
  }, []);

  const handleOpenNotifications = useCallback((open: boolean): void => {
    dispatch({ type: 'setOpen', open });
  }, []);

  const setUnreadCount = useCallback((count: number): void => {
    dispatch({ type: 'setUnreadCount', count });
  }, []);

  return {
    notifications: state.notifications,
    notificationsOpen: state.notificationsOpen,
    unreadCount: state.unreadCount,
    setNotificationsOpen: handleOpenNotifications,
    pushNotification,
    clearNotifications,
    setUnreadCount,
  };
}
