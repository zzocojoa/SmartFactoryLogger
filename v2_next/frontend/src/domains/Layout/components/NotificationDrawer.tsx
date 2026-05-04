import React from 'react';
import { NotificationItem } from '../../../shared/types';

export interface NotificationDrawerProps {
  notifications: NotificationItem[];
  notificationsOpen: boolean;
  setNotificationsOpen: (open: boolean) => void;
  clearNotifications: () => void;
}

const getNotificationStateText = (item: NotificationItem): string | null => {
  if (item.lifecycle === 'active') {
    return '진행 중';
  }

  if (item.lifecycle === 'resolved') {
    return '해결됨';
  }

  if (item.lifecycle === 'history') {
    return '기록';
  }

  return null;
};

const getNotificationTimeText = (item: NotificationItem): string => {
  return new Date(item.time).toLocaleTimeString();
};

const getNotificationTitleText = (item: NotificationItem): string => {
  const stateText = getNotificationStateText(item);
  if (stateText === null) {
    return item.title;
  }

  return `${item.title} [${stateText}]`;
};

export const NotificationDrawer: React.FC<NotificationDrawerProps> = ({
  notifications,
  notificationsOpen,
  setNotificationsOpen,
  clearNotifications,
}) => {
  return (
    <div
      className={`notification-overlay ${notificationsOpen ? 'open' : ''}`}
      onClick={() => setNotificationsOpen(false)}
    >
      <div
        className={`notification-drawer ${notificationsOpen ? 'open' : ''}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="notification-header">
          <span>알림 내역</span>
          <div className="notification-actions">
            <button onClick={clearNotifications} className="notification-action">
              모두 지우기
            </button>
            <button onClick={() => setNotificationsOpen(false)} className="notification-action">
              닫기
            </button>
          </div>
        </div>
        <div className="notification-list">
          {notifications.length === 0 ? (
            <div className="notification-empty">알림이 없습니다.</div>
          ) : (
            notifications.map((item) => (
              <div key={item.id} className={`notification-item ${item.level}`}>
                <div className="notification-item-header">
                  <span className="notification-title">{getNotificationTitleText(item)}</span>
                  <span className="notification-time">
                    {getNotificationTimeText(item)}
                  </span>
                </div>
                <div className="notification-message">{item.message}</div>
                {item.detail ? (
                  <div className="notification-message">{item.detail}</div>
                ) : null}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
