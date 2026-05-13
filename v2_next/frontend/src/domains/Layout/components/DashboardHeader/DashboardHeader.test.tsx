import React from 'react';
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { DashboardHeaderProps } from './DashboardHeader';
import { DashboardHeader } from './DashboardHeader';

const buildProps = (overrides: Partial<DashboardHeaderProps> = {}): DashboardHeaderProps => ({
  activeCycle: 'day',
  appTitle: '창녕 2호기 Smart Factory',
  statusLabel: 'Running',
  statusClass: 'status-ok',
  statusTitle: 'System running',
  lastUpdateText: '14:19:47',
  avgLatencyText: '2ms',
  errorCountText: '0',
  errorQueueText: '0',
  errorQueueTitle: 'No queued errors',
  commBadges: [
    { key: 'EX', text: 'EX OK', title: 'EX OK', state: 'ok' },
    { key: 'LS', text: 'LS OK', title: 'LS OK', state: 'ok' },
    { key: 'SPOT', text: 'SPOT OK', title: 'SPOT OK', state: 'ok' },
  ],
  handleSnapshot: vi.fn(),
  snapshotLoading: false,
  handleReconnect: vi.fn(),
  reconnectBusy: false,
  handleDiagnosis: vi.fn(),
  diagnosisBusy: false,
  settingsForm: null,
  unreadCount: 0,
  notificationsOpen: false,
  setNotificationsOpen: vi.fn(),
  setUnreadCount: vi.fn(),
  clearNotifications: vi.fn(),
  menuOpen: false,
  setMenuOpen: vi.fn(),
  menuRef: React.createRef<HTMLDivElement>(),
  widgetAddOpen: false,
  setWidgetAddOpen: vi.fn(),
  presetOpen: false,
  setPresetOpen: vi.fn(),
  layoutEditing: false,
  setLayoutEditing: vi.fn(),
  storageMode: 'local',
  setStorageMode: vi.fn(),
  saveLayout: vi.fn(),
  restoreLayout: vi.fn(),
  deleteLayoutSlot: vi.fn(),
  layoutSlots: [],
  layoutActiveId: null,
  layoutRestoreMessage: null,
  layoutSaveMessage: null,
  layoutSaveError: null,
  layoutRestoreError: null,
  handleAddWidget: vi.fn(),
  applyPreset: vi.fn(),
  themeMode: 'auto',
  setThemeMode: vi.fn(),
  handleOpenSettings: vi.fn(),
  ...overrides,
});

afterEach(() => {
  cleanup();
});

describe('DashboardHeader mobile header', () => {
  it('keeps full comm labels accessible while exposing short mobile labels', () => {
    const { container } = render(<DashboardHeader {...buildProps()} />);

    expect(screen.getByLabelText('EX OK')).toBeInTheDocument();
    expect(screen.getByLabelText('LS OK')).toBeInTheDocument();
    expect(screen.getByLabelText('SPOT OK')).toBeInTheDocument();

    const shortLabels = Array.from(container.querySelectorAll('.status-comm-label-mobile'))
      .map((element) => element.textContent);

    expect(shortLabels).toEqual(['EX', 'LS', 'SPOT']);
  });

  it('connects the hamburger button to the detail drawer', () => {
    render(<DashboardHeader {...buildProps({ menuOpen: true })} />);

    const menuButton = screen.getByRole('button', { name: '상세 메뉴 닫기' });

    expect(menuButton).not.toHaveAttribute('aria-pressed');
    expect(menuButton).toHaveAttribute('aria-expanded', 'true');
    expect(menuButton).toHaveAttribute('aria-controls', 'dashboard-menu-drawer');
    expect(screen.getByRole('region', { name: '상세 메뉴' })).toHaveAttribute('id', 'dashboard-menu-drawer');
  });

  it('removes the closed drawer from the accessibility tree and tab flow', () => {
    const { container } = render(<DashboardHeader {...buildProps({ menuOpen: false })} />);

    expect(screen.queryByRole('region', { name: '상세 메뉴' })).not.toBeInTheDocument();

    const drawer = container.querySelector('#dashboard-menu-drawer');

    expect(drawer).toHaveAttribute('aria-hidden', 'true');
    expect(drawer).toHaveAttribute('hidden');
  });

  it('keeps detailed status content available inside the open drawer', () => {
    render(<DashboardHeader {...buildProps({ menuOpen: true })} />);

    const drawer = screen.getByRole('region', { name: '상세 메뉴' });
    const drawerScope = within(drawer);

    expect(drawerScope.getByText('창녕 2호기 Smart Factory')).toBeInTheDocument();
    expect(drawerScope.getByText('Running')).toBeInTheDocument();
    expect(drawerScope.getByText('Last')).toBeInTheDocument();
    expect(drawerScope.getByText('Avg')).toBeInTheDocument();
    expect(drawerScope.getByText('Errors')).toBeInTheDocument();
    expect(drawerScope.getByText('ErrQ')).toBeInTheDocument();
    expect(drawerScope.getByText('EX OK')).toBeInTheDocument();
    expect(drawerScope.getByText('LS OK')).toBeInTheDocument();
    expect(drawerScope.getByText('SPOT OK')).toBeInTheDocument();
  });

  it('keeps hidden mobile header actions reachable from the drawer', () => {
    render(<DashboardHeader {...buildProps({ menuOpen: true })} />);

    expect(screen.getAllByRole('button', { name: 'Snapshot' })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: 'Reconnect' })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: 'Diagnosis' })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: '알림' })).toHaveLength(2);
  });

  it('closes the menu drawer when the drawer notification action opens notifications', () => {
    const setMenuOpen = vi.fn();
    const setNotificationsOpen = vi.fn();
    const setUnreadCount = vi.fn();
    render(<DashboardHeader {...buildProps({
      menuOpen: true,
      setMenuOpen,
      setNotificationsOpen,
      setUnreadCount,
    })} />);

    const drawer = screen.getByRole('region', { name: '상세 메뉴' });

    fireEvent.click(within(drawer).getByRole('button', { name: '알림' }));

    expect(setNotificationsOpen).toHaveBeenCalledWith(true);
    expect(setUnreadCount).toHaveBeenCalledWith(0);
    expect(setMenuOpen).toHaveBeenCalledWith(false);
  });

  it('closes the drawer on Escape and returns focus to the menu button', () => {
    const setMenuOpen = vi.fn();
    render(<DashboardHeader {...buildProps({ menuOpen: true, setMenuOpen })} />);

    const menuButton = screen.getByRole('button', { name: '상세 메뉴 닫기' });

    fireEvent.keyDown(window, { key: 'Escape' });

    expect(setMenuOpen).toHaveBeenCalledWith(false);
    expect(menuButton).toHaveFocus();
  });
});
