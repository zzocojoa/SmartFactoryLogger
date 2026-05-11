import {
  LayoutSlotSummary,
  SettingsFormState,
} from '../../../../shared/types';
import type { WidgetType } from '../../../../scenes/DashboardSceneModel';
import type { LayoutPresetId } from '../../../../shared/constants/layoutPresets';
import { APP_TITLE } from '../../../../shared/constants/uiText';
import { CommBadge } from '../../../../shared/utils/commBadge';
import { formatMetaTime } from '../../../../shared/utils/formatters';

const resolvePublicAssetPath = (assetPath: string): string => {
  const normalizedAssetPath = assetPath.replace(/^\/+/, '');

  if (window.location.protocol === 'file:') {
    return `./${normalizedAssetPath}`;
  }

  return `/${normalizedAssetPath}`;
};

const resolveLogoSource = (activeCycle: string): string => {
  const logoPath = activeCycle === 'day' || activeCycle === 'sunset'
    ? 'assets/logo_color.png'
    : 'assets/logo_white.png';

  return resolvePublicAssetPath(logoPath);
};

export interface DashboardHeaderProps {
  activeCycle: string;
  appTitle?: string;
  statusLabel: string;
  statusClass: string;
  statusTitle: string;
  lastUpdateText: string;
  avgLatencyText: string;
  errorCountText: string;
  errorQueueText: string;
  errorQueueTitle: string;
  commBadges: CommBadge[];
  handleSnapshot: () => void;
  snapshotLoading: boolean;
  handleReconnect: () => void;
  reconnectBusy: boolean;
  handleDiagnosis: () => void;
  diagnosisBusy: boolean;
  settingsForm: SettingsFormState | null;
  unreadCount: number;
  notificationsOpen: boolean;
  setNotificationsOpen: (open: boolean) => void;
  setUnreadCount: (count: number) => void;
  clearNotifications: () => void;
  menuOpen: boolean;
  setMenuOpen: React.Dispatch<React.SetStateAction<boolean>>;
  menuRef: React.RefObject<HTMLDivElement | null>;
  widgetAddOpen: boolean;
  setWidgetAddOpen: (open: boolean) => void;
  presetOpen: boolean;
  setPresetOpen: (open: boolean) => void;
  layoutEditing: boolean;
  setLayoutEditing: (editing: boolean) => void;
  storageMode: 'local' | 'server';
  setStorageMode: (mode: 'local' | 'server') => void;
  saveLayout: () => void;
  restoreLayout: (id?: string) => void;
  deleteLayoutSlot: (id: string) => void;
  layoutSlots: LayoutSlotSummary[];
  layoutActiveId: string | null;
  layoutRestoreMessage: string | null;
  layoutSaveMessage: string | null;
  layoutSaveError: string | null;
  layoutRestoreError: string | null;
  handleAddWidget: (type: WidgetType) => void;
  applyPreset: (preset: LayoutPresetId) => void;
  themeMode: 'light' | 'dark' | 'auto';
  setThemeMode: (mode: 'light' | 'dark' | 'auto') => void;
  handleOpenSettings: () => void;
}

export const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  activeCycle,
  appTitle = APP_TITLE,
  statusLabel,
  statusClass,
  statusTitle,
  lastUpdateText,
  avgLatencyText,
  errorCountText,
  errorQueueText,
  errorQueueTitle,
  commBadges,
  handleSnapshot,
  snapshotLoading,
  handleReconnect,
  reconnectBusy,
  handleDiagnosis,
  diagnosisBusy,
  settingsForm,
  unreadCount,
  notificationsOpen,
  setNotificationsOpen,
  setUnreadCount,
  menuOpen,
  setMenuOpen,
  menuRef,
  widgetAddOpen,
  setWidgetAddOpen,
  presetOpen,
  setPresetOpen,
  layoutEditing,
  setLayoutEditing,
  storageMode,
  setStorageMode,
  saveLayout,
  restoreLayout,
  deleteLayoutSlot,
  layoutSlots,
  layoutActiveId,
  layoutRestoreMessage,
  layoutSaveMessage,
  layoutSaveError,
  layoutRestoreError,
  handleAddWidget,
  applyPreset,
  themeMode,
  setThemeMode,
  handleOpenSettings,
}) => {
  return (
    <header className="app-header">
      <div className="app-brand">
        <img
          src={resolveLogoSource(activeCycle)}
          alt="Company Logo"
          className="app-logo"
        />
        <h1>{appTitle}</h1>
      </div>
      <div className="header-controls">
        <div className="status-panel" title={statusTitle}>
          <div className={`status-badge ${statusClass}`}>{statusLabel}</div>
          <div className="status-meta">
            <span className="status-meta-item">
              <span className="status-meta-label">Last</span>
              <span className="status-meta-value">{lastUpdateText}</span>
            </span>
            <span className="status-meta-item">
              <span className="status-meta-label">Avg</span>
              <span className="status-meta-value">{avgLatencyText}</span>
            </span>
            <span className="status-meta-item">
              <span className="status-meta-label">Errors</span>
              <span className="status-meta-value">{errorCountText}</span>
            </span>
            <span className="status-meta-item" title={errorQueueTitle}>
              <span className="status-meta-label">ErrQ</span>
              <span className="status-meta-value">{errorQueueText}</span>
            </span>
          </div>
          {commBadges.length > 0 && (
            <div className="status-comm">
              {commBadges.map((badge) => (
                <span
                  key={badge.key}
                  className={`status-comm-item ${badge.state}`}
                  title={badge.title}
                >
                  {badge.text}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="snapshot-control">
          <button
            className={`status-action ${snapshotLoading ? 'loading' : ''}`}
            onClick={handleSnapshot}
            disabled={snapshotLoading}
            aria-disabled={snapshotLoading}
            title={settingsForm?.snapshotPath ? `Save to: ${settingsForm.snapshotPath}` : 'Snapshot'}
          >
            Snapshot
          </button>
        </div>

        <div className="status-actions">
          <button
            className="status-action"
            onClick={handleReconnect}
            disabled={reconnectBusy}
            aria-disabled={reconnectBusy}
          >
            Reconnect
          </button>
          <button
            className="status-action"
            onClick={handleDiagnosis}
            disabled={diagnosisBusy}
            aria-disabled={diagnosisBusy}
          >
            Diagnosis
          </button>
        </div>

        <button
          className="notify-bell"
          onClick={() => {
            const nextState = !notificationsOpen;
            setNotificationsOpen(nextState);
            if (nextState) {
              setUnreadCount(0);
            }
          }}
          aria-pressed={notificationsOpen}
        >
          알림
          {unreadCount > 0 && <span className="notify-badge">{unreadCount}</span>}
        </button>

        <div className="menu-wrapper" ref={menuRef as React.RefObject<HTMLDivElement>}>
          <button
            className="menu-toggle"
            onClick={() => setMenuOpen((prev) => !prev)}
            aria-pressed={menuOpen}
          >
            MENU
          </button>
          <div className={`menu-dropdown ${menuOpen ? 'open' : ''}`}>
            <button
              className="menu-item"
              onClick={() => {
                setLayoutEditing(!layoutEditing);
              }}
            >
              {layoutEditing ? '편집 완료' : '편집 모드'}
            </button>

            {layoutEditing ? (
              <>
                <div className="menu-dropdown-section">
                  <div className="menu-section-title">저장 위치</div>
                  <div className="menu-storage-toggle">
                    <button
                      className={`menu-item menu-storage-btn ${storageMode === 'local' ? 'active' : ''}`}
                      onClick={() => setStorageMode('local')}
                    >
                      로컬 PC
                    </button>
                    <button
                      className={`menu-item menu-storage-btn ${storageMode === 'server' ? 'active' : ''}`}
                      onClick={() => setStorageMode('server')}
                    >
                      서버
                    </button>
                  </div>
                </div>

                <button
                  onClick={() => {
                    saveLayout();
                    setMenuOpen(false);
                  }}
                  className="menu-item"
                >
                  레이아웃 저장
                </button>

                <div className="menu-layout-list">
                  <div className="menu-section-title">
                    저장된 레이아웃 {storageMode === 'local' ? '(로컬)' : '(서버)'}
                  </div>
                  {layoutSlots.length > 0 ? (
                    layoutSlots.map((slot) => (
                      <div
                        key={slot.id}
                        className={`menu-layout-row ${slot.id === layoutActiveId ? 'active' : ''}`}
                      >
                        <button
                          className="menu-item menu-layout-button"
                          onClick={() => restoreLayout(slot.id)}
                        >
                          복구
                        </button>
                        <button
                          className="menu-item menu-layout-button menu-layout-delete"
                          onClick={() => deleteLayoutSlot(slot.id)}
                        >
                          삭제
                        </button>
                        <div className="menu-layout-meta">
                          <div className="menu-layout-title">
                            <span className="menu-layout-name">{slot.name}</span>
                            {slot.id === layoutActiveId && (
                              <span className="menu-layout-active">현재</span>
                            )}
                          </div>
                          <span className="menu-layout-time">{formatMetaTime(slot.updated_at)}</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="menu-layout-empty">저장된 레이아웃이 없습니다.</div>
                  )}
                  {layoutRestoreMessage && (
                    <div className="menu-layout-message">{layoutRestoreMessage}</div>
                  )}
                  {layoutSaveMessage && (
                    <div className="menu-layout-message">{layoutSaveMessage}</div>
                  )}
                </div>

                <div className="menu-divider" />

                <div className="menu-accordion">
                  <button
                    className={`menu-accordion-header ${widgetAddOpen ? 'open' : ''}`}
                    onClick={() => setWidgetAddOpen(!widgetAddOpen)}
                  >
                    <span>위젯 추가</span>
                    <span className="menu-accordion-icon">{widgetAddOpen ? '▾' : '▸'}</span>
                  </button>
                  {widgetAddOpen && (
                    <div className="menu-accordion-content">
                      <button className="menu-item" onClick={() => handleAddWidget('markdown')}>
                        메모
                      </button>
                      <button className="menu-item" onClick={() => handleAddWidget('timeseries')}>
                        시계열
                      </button>
                      <button className="menu-item" onClick={() => handleAddWidget('kpi')}>
                        KPI
                      </button>
                      <button className="menu-item" onClick={() => handleAddWidget('spot')}>
                        SPOT 온도
                      </button>
                      <button className="menu-item" onClick={() => handleAddWidget('camera')}>
                        SPOT 카메라
                      </button>
                      <button className="menu-item" onClick={() => handleAddWidget('temps')}>
                        보조 온도
                      </button>
                      <button className="menu-item" onClick={() => handleAddWidget('molds')}>
                        금형
                      </button>
                      <button className="menu-item" onClick={() => handleAddWidget('env')}>
                        환경
                      </button>
                    </div>
                  )}
                </div>

                <div className="menu-divider" />

                <div className="menu-accordion">
                  <button
                    className={`menu-accordion-header ${presetOpen ? 'open' : ''}`}
                    onClick={() => setPresetOpen(!presetOpen)}
                  >
                    <span>화면 비율 프리셋</span>
                    <span className="menu-accordion-icon">{presetOpen ? '▾' : '▸'}</span>
                  </button>
                  {presetOpen && (
                    <div className="menu-accordion-content">
                      <button className="menu-item" onClick={() => applyPreset('16:9')}>
                        16:9 일반
                      </button>
                      <button className="menu-item" onClick={() => applyPreset('21:9')}>
                        21:9 와이드
                      </button>
                      <button className="menu-item" onClick={() => applyPreset('4:3')}>
                        4:3 클래식
                      </button>
                      <button className="menu-item" onClick={() => applyPreset('compact')}>
                        컴팩트
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : null}

            <div className="menu-divider" />
            <button
              className="menu-item"
              onClick={handleOpenSettings}
            >
              설정
            </button>

            {layoutEditing && layoutSaveError && (
              <div className="menu-error">
                <span>{layoutSaveError}</span>
                <button onClick={saveLayout} className="retry-button">
                  다시 시도
                </button>
              </div>
            )}

            {layoutEditing && layoutRestoreError && (
              <div className="menu-error">
                <span>{layoutRestoreError}</span>
                <button onClick={() => restoreLayout()} className="retry-button">
                  다시 시도
                </button>
              </div>
            )}

            <div style={{ margin: '8px 0', borderBottom: '1px solid var(--border-muted)' }} />
            <div
              className="menu-section-title"
              style={{ padding: '4px 12px', fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}
            >
              테마 설정
            </div>
            <div style={{ padding: '0 12px 12px 12px', display: 'flex', gap: '8px' }}>
              <button
                className={`custom-modal-btn ${themeMode === 'light' ? 'confirm' : 'cancel'}`}
                onClick={() => setThemeMode('light')}
                style={{ flex: 1, padding: '6px 0', fontSize: '0.8rem', justifyContent: 'center' }}
              >
                Light
              </button>
              <button
                className={`custom-modal-btn ${themeMode === 'dark' ? 'confirm' : 'cancel'}`}
                onClick={() => setThemeMode('dark')}
                style={{ flex: 1, padding: '6px 0', fontSize: '0.8rem', justifyContent: 'center' }}
              >
                Dark
              </button>
              <button
                className={`custom-modal-btn ${themeMode === 'auto' ? 'confirm' : 'cancel'}`}
                onClick={() => setThemeMode('auto')}
                style={{ flex: 1, padding: '6px 0', fontSize: '0.8rem', justifyContent: 'center' }}
              >
                Auto
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
