import React from 'react';
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { FactoryData, HealthSnapshot, StatsSnapshot } from '../../../../shared/types';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import type { StatusPanelSource } from '../../hooks/useStatusPanel';
import type { DashboardHeaderProps } from './DashboardHeader';
import { DashboardHeader } from './DashboardHeader';

const appCss = readFileSync(resolve(process.cwd(), 'src/App.css'), 'utf8');

const getCssRuleBody = (selector: string): string => {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = appCss.match(new RegExp(`${escapedSelector}\\s*\\{([^}]*)\\}`));

  if (!match) {
    throw new Error(`CSS rule not found: ${selector}`);
  }

  return match[1];
};

const buildHealthSnapshot = (): HealthSnapshot => ({
  running: true,
  thread_alive: true,
  last_update: Math.floor(Date.now() / 1000),
  driver_connected: true,
  mode: 'auto',
  spot_temperature: {
    spot_poll_status: 'success', spot_raw_validity: 'valid_temperature', spot_source_freshness: 'fresh',
    temperature_value_origin: 'current_observation', spot_snapshot_age_ms: 0,
  },
  comm: {
    extruder: { connected: true, last_success_time: Date.now() / 1000 },
    ls_plc: { connected: true, last_success_time: Date.now() / 1000 },
    spot: { last_value: 18, last_success_time: Date.now() / 1000 },
  },
});

const buildStatsSnapshot = (): StatsSnapshot => ({
  uptime_sec: 10,
  total_requests: 10,
  avg_latency_ms: 2,
  error_count: 0,
  last: {
    latency_ms: 2,
    path: '/api/latest',
    status: 200,
    timestamp: Date.now() / 1000,
  },
  window: {
    window_sec: 60,
    request_count: 10,
    error_count: 0,
    http_error_count: 0,
    http_4xx_count: 0,
    http_5xx_count: 0,
    error_rate: 0,
    avg_latency_ms: 2,
    p95_latency_ms: 3,
  },
  errors: {
    queue_size: 0,
    last_error_at: null,
    source_counts: {},
  },
});

const buildStatusPanelSource = (): StatusPanelSource => ({
  health: buildHealthSnapshot(),
  healthReceipt: { receivedAtMonotonicMs: performance.now(), ageAtReceiptMs: 0 },
  stats: buildStatsSnapshot(),
  healthPollingDegraded: false,
  healthPollingIntervalMs: 1000,
  healthPollingFailureCount: 0,
  statsPollingDegraded: false,
  statsPollingIntervalMs: 1000,
  statsPollingFailureCount: 0,
  spotConfig: null,
  spotImageUrl: '',
  spotImageLoading: false,
  spotImageError: null,
  spotLastSuccessAt: null,
  spotImageMetadata: null,
  settingsBaseline: null,
});

const buildFactoryData = (overrides: Partial<FactoryData> = {}): FactoryData => ({
  Time: '2026-03-09T07:20:20.000',
  Status: 'Running',
  Speed: 1,
  Press: 2,
  Count: 3,
  EndPos: 4,
  Billet_Length: 5,
  Spot: 6,
  Temp_F: 7,
  Temp_B: 8,
  Billet_Temp: 9,
  Mold1: 10,
  Mold2: 11,
  Mold3: 12,
  Mold4: 13,
  Mold5: 14,
  Mold6: 15,
  At_Temp: 16,
  At_Pre: 17,
  ...overrides,
});

const buildProps = (overrides: Partial<DashboardHeaderProps> = {}): DashboardHeaderProps => ({
  activeCycle: 'day',
  appTitle: '창녕 2호기 Smart Factory',
  statusPanelSource: buildStatusPanelSource(),
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
  pushNotification: vi.fn(),
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
  useDashboardStore.getState().setData(null, null);
});

describe('DashboardHeader mobile header', () => {
  it('keeps full comm labels accessible while exposing short mobile labels', () => {
    const { container } = render(<DashboardHeader {...buildProps()} />);

    expect(screen.getByLabelText('EX OK')).toBeInTheDocument();
    expect(screen.getByLabelText('LS OK')).toBeInTheDocument();
    expect(screen.getByLabelText('SPOT OK')).toBeInTheDocument();
    expect(screen.getByLabelText('Temp OK')).toBeInTheDocument();

    const shortLabels = Array.from(container.querySelectorAll('.status-comm-label-mobile'))
      .map((element) => element.textContent);

    expect(shortLabels).toEqual(['EX', 'LS', 'SPOT', 'Temp OK']);
  });

  it('R10b keeps the measurement state in the compact temperature label', () => {
    const source = buildStatusPanelSource();
    source.health!.spot_temperature = {...source.health!.spot_temperature,
      spot_raw_validity: 'invalid_sentinel', spot_device_status_code: 'temperature_under_range',
      temperature_value_origin: 'none', temperature_status_shadow: 'invalid_value'};
    const {container} = render(<DashboardHeader {...buildProps({statusPanelSource: source})} />);
    expect(container.querySelector('.status-temperature .status-comm-label-mobile')).toHaveTextContent('UNDER_RANGE');
    expect(screen.getByText('Comm OK')).toHaveClass('ok');
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
    expect(drawerScope.getByText('Status details')).toBeInTheDocument();
    expect(drawerScope.getByText('Running')).toBeInTheDocument();
    expect(drawerScope.getByText('Last')).toBeInTheDocument();
    expect(drawerScope.getByText('Avg')).toBeInTheDocument();
    expect(drawerScope.getByText('Errors')).toBeInTheDocument();
    expect(drawerScope.getByText('ErrQ')).toBeInTheDocument();
    expect(drawerScope.getByText('EX OK')).toBeInTheDocument();
    expect(drawerScope.getByText('LS OK')).toBeInTheDocument();
    expect(drawerScope.getByText('SPOT OK')).toBeInTheDocument();
    expect(drawerScope.getByText('Temp OK')).toBeInTheDocument();
  });

  it('excludes under-range temperature from Comm and exposes both labels in the drawer', () => {
    const source = buildStatusPanelSource();
    source.health!.spot_temperature = { ...source.health!.spot_temperature,
      spot_raw_validity: 'invalid_sentinel', spot_device_status_code: 'temperature_under_range',
      temperature_value_origin: 'none', temperature_status_shadow: 'invalid_value' };
    render(<DashboardHeader {...buildProps({ statusPanelSource: source, menuOpen: true })} />);
    expect(screen.getByLabelText('SPOT OK')).toHaveClass('ok');
    expect(screen.getByLabelText('Temp UNDER_RANGE')).toHaveClass('warn');
    expect(screen.getByText('Comm OK')).toHaveClass('ok');
    expect(screen.getByLabelText('Temp UNDER_RANGE')).toHaveAttribute('title', expect.stringContaining('temperature_under_range'));
    const drawer = within(screen.getByRole('region', { name: '상세 메뉴' }));
    expect(drawer.getByText('SPOT OK')).toBeInTheDocument();
    expect(drawer.getByText('Temp UNDER_RANGE')).toBeInTheDocument();
    const diagnostics = drawer.getByLabelText('SPOT 진단 상세');
    const rows = Array.from(diagnostics.querySelectorAll('div')).map(row => ({
      label: row.querySelector('dt')?.textContent, value: row.querySelector('dd')?.textContent,
    }));
    expect(rows).toEqual(expect.arrayContaining([
      {label: 'poll', value: 'success'}, {label: 'raw', value: 'invalid_sentinel'},
      {label: 'source', value: 'fresh'}, {label: '장비', value: 'temperature_under_range'},
      {label: '온도 상태', value: 'invalid_value'}, {label: 'origin', value: 'none'},
      {label: 'cache', value: 'unknown'}, {label: '관측 경과', value: expect.stringMatching(/^\d+\.\d+s$/)},
      {label: '최근 유효 온도', value: expect.any(String)}, {label: '최근 오류', value: '--:--:--'},
    ]));
    const tooltip = screen.getByLabelText('Temp UNDER_RANGE').getAttribute('title');
    rows.forEach(({label, value}) => expect(tooltip).toContain(`${label} ${value}`));
  });

  it('keeps diagnostics out of the topbar while grouping drawer commands', () => {
    const { container } = render(<DashboardHeader {...buildProps({ menuOpen: true })} />);

    const topbarCommands = container.querySelector('.header-command-group');
    expect(topbarCommands).not.toBeNull();
    expect(container.querySelector('.header-command-group > .status-actions')).not.toBeInTheDocument();
    expect(container.querySelector('.header-controls .status-meta')).not.toBeInTheDocument();

    const drawer = container.querySelector('#dashboard-menu-drawer');
    expect(drawer).not.toBeNull();
    const drawerScope = within(drawer as HTMLElement);

    expect(drawerScope.getByText('Commands')).toBeInTheDocument();
    expect(drawerScope.getByRole('button', { name: 'Reconnect' })).toBeInTheDocument();
    expect(drawerScope.getByRole('button', { name: 'Diagnosis' })).toBeInTheDocument();
  });

  it('keeps overflow drawer details visible outside compact media queries', () => {
    expect(getCssRuleBody('.mobile-menu-comm .status-temperature')).toMatch(/white-space:\s*normal/);
    expect(getCssRuleBody('.mobile-menu-spot-details dd')).toMatch(/overflow-wrap:\s*anywhere/);
    expect(getCssRuleBody('.mobile-menu-details')).toMatch(/display:\s*flex/);
    expect(getCssRuleBody('.mobile-menu-details')).not.toMatch(/display:\s*none/);
    expect(getCssRuleBody('.header-overflow-section')).toMatch(/display:\s*flex/);
    expect(appCss).toMatch(
      /@media \(max-width: 520px\)[\s\S]*\.status-comm \.status-comm-item:not\(\.status-comm-summary\)\s*\{[\s\S]*display:\s*none/
    );
    expect(appCss).toMatch(
      /@media \(max-width: 520px\)[\s\S]*\.status-comm-summary\s*\{[\s\S]*display:\s*inline-flex/
    );
  });

  it('clips operator alert decoration without restoring global scene overflow clipping', () => {
    const alertGlowRule = getCssRuleBody('.operator-card-alert-glow');

    expect(alertGlowRule).toMatch(/inset:\s*0/);
    expect(alertGlowRule).toMatch(/overflow:\s*hidden/);
    expect(alertGlowRule).toMatch(/contain:\s*paint/);
    expect(appCss).not.toMatch(
      /\.App:not\(\.layout-editing\)\s+\.scene-container\s*\{[^}]*overflow-x:\s*hidden/
    );
  });

  it('shows a required operator metadata indicator when the latest sample is invalid', () => {
    useDashboardStore.getState().setData(buildFactoryData({
      Product_No_operator: '',
      Mold_No_operator: '',
      operator_metadata_valid: false,
      operator_metadata_missing_fields: ['product_no', 'operator_mold_no'],
      operator_metadata_updated_at: '2026-03-09T07:20:20Z',
    }), Date.now());

    render(<DashboardHeader {...buildProps()} />);

    expect(screen.getByLabelText('Operator metadata required')).toHaveClass('attention');
  });

  it('shows an applied operator metadata indicator when the latest sample is valid', () => {
    useDashboardStore.getState().setData(buildFactoryData({
      Product_No_operator: '12345',
      Mold_No_operator: '123',
      operator_metadata_valid: true,
      operator_metadata_missing_fields: [],
      operator_metadata_updated_at: '2026-03-09T07:20:20Z',
    }), Date.now());

    render(<DashboardHeader {...buildProps()} />);

    expect(screen.getByLabelText('Operator metadata applied')).toHaveClass('ok');
  });

  it('keeps hidden mobile header actions reachable from the drawer', () => {
    render(<DashboardHeader {...buildProps({ menuOpen: true })} />);

    expect(screen.getAllByRole('button', { name: 'Snapshot' })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: 'Reconnect' })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: 'Diagnosis' })).toHaveLength(1);
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

  it('routes the operator metadata add action from the edit menu', () => {
    const handleAddWidget = vi.fn();
    render(<DashboardHeader {...buildProps({
      menuOpen: true,
      layoutEditing: true,
      widgetAddOpen: true,
      handleAddWidget,
    })} />);

    fireEvent.click(screen.getByRole('button', { name: 'Add operator metadata widget' }));

    expect(handleAddWidget).toHaveBeenCalledWith('operatorMetadata');
  });
});
