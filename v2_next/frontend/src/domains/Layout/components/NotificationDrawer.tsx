import React from 'react';
import { NotificationItem } from '../../../shared/types';

export interface NotificationDrawerProps {
  notifications: NotificationItem[];
  notificationsOpen: boolean;
  setNotificationsOpen: (open: boolean) => void;
  clearNotifications: () => void;
}

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
                  <span className="notification-title">{item.title}</span>
                  <span className="notification-time">
                    {new Date(item.time).toLocaleTimeString()}
                  </span>
                </div>
                <div className="notification-message">{item.message}</div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
