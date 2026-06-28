import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type {
  FrontendMemorySnapshot,
  MemoryCollectorDeltaItem,
  MemoryDetailsResponse,
  MemoryGCSnapshot,
  MemoryLeakSuspect,
} from '../../../../shared/types';
import { MemorySection } from './MemorySection';

const noop = () => undefined;

const buildCollector = (overrides: Partial<MemoryCollectorDeltaItem>): MemoryCollectorDeltaItem => ({
  name: 'backend.collector',
  kind: 'snapshot',
  exactness: 'estimated',
  bytes: 1024,
  delta_bytes: 0,
  share_ratio: 1,
  items: 1,
  note: 'sample',
  ...overrides,
});

const buildDetails = (
  collectors: MemoryCollectorDeltaItem | MemoryCollectorDeltaItem[],
  leakSuspects: MemoryLeakSuspect[] = [],
  latestGcSnapshot: MemoryGCSnapshot | null = null
): MemoryDetailsResponse => ({
  backend_top_consumers: [],
  backend_growth: Array.isArray(collectors) ? collectors : [collectors],
  collector_history: [],
  leak_suspects: leakSuspects,
  latest_gc_snapshot: latestGcSnapshot,
  latest_tracemalloc_diff: [],
});

const renderMemorySection = (
  backendMemoryDetails: MemoryDetailsResponse,
  overrides: Partial<React.ComponentProps<typeof MemorySection>> = {}
) => {
  return render(
    <MemorySection
      health={null}
      backendMemory={null}
      backendMemoryDetails={backendMemoryDetails}
      frontendMemory={null}
      memorySummaryBusy={false}
      memoryDetailsBusy={false}
      memoryRefreshInFlight={false}
      memoryRefreshIntervalMs={5000}
      profilerStartBusy={false}
      profilerStopBusy={false}
      memoryExportBusy={false}
      memoryExportPath={null}
      memoryLeader={null}
      memoryActionState={{
        refresh: false,
        snapshot: false,
        profiler_action: null,
        export: false,
      }}
      lastExportAt={null}
      lastSummaryAt={null}
      lastDetailsAt={null}
      lastExportMetaAt={null}
      summaryRequestCount={0}
      detailsRequestCount={0}
      lastSummaryReason={null}
      onRefresh={noop}
      onStartProfiler={noop}
      onStopProfiler={noop}
      onSnapshot={noop}
      onGc={noop}
      onExport={noop}
      onOpenFile={noop}
      onOpenFolder={noop}
      onCopyPath={noop}
      {...overrides}
    />
  );
};

afterEach(() => {
  cleanup();
});

describe('MemorySection collector runtime contract', () => {
  it('renders old backend collector payloads without runtime fields', () => {
    renderMemorySection(buildDetails(buildCollector({ name: 'legacy.collector' })));

    expect(screen.getByText('Backend growth')).toBeInTheDocument();
    expect(screen.getByText('legacy.collector')).toBeInTheDocument();
  });

  it('renders optional collector status and latency fields', () => {
    renderMemorySection(
      buildDetails(
        buildCollector({
          name: 'slow.collector',
          latency_ms: 12.345,
          status: 'slow',
          stale: false,
          source: 'backend',
        })
      )
    );

    expect(screen.getByText('slow.collector')).toBeInTheDocument();
    expect(screen.getByText('slow')).toBeInTheDocument();
    expect(screen.getByText('12.3 ms')).toBeInTheDocument();
  });

  it('renders critical severity before larger size or delta by default', () => {
    renderMemorySection(
      buildDetails([
        buildCollector({
          name: 'ok.large-delta',
          bytes: 10 * 1024 * 1024,
          delta_bytes: 9 * 1024 * 1024,
          severity: 'ok',
        }),
        buildCollector({
          name: 'warn.small-delta',
          bytes: 2 * 1024 * 1024,
          delta_bytes: 1,
          severity: 'warn',
        }),
        buildCollector({
          name: 'critical.medium-delta',
          bytes: 4 * 1024 * 1024,
          delta_bytes: 1024,
          severity: 'critical',
        }),
      ])
    );

    const rowNames = Array.from(document.querySelectorAll('.settings-memory-cell-strong'))
      .map((element) => element.textContent)
      .filter((value): value is string => Boolean(value));

    expect(rowNames.slice(0, 3)).toEqual(['critical.medium-delta', 'warn.small-delta', 'ok.large-delta']);
    expect(screen.getByText('critical')).toBeInTheDocument();
    expect(screen.getByText('warn')).toBeInTheDocument();
  });

  it('renders leak suspect section with empty state when no suspects are present', () => {
    renderMemorySection(buildDetails(buildCollector({ name: 'ok.collector' })));

    expect(screen.getAllByText('누수 의심').length).toBeGreaterThan(0);
    expect(screen.getByText('누수 의심 없음')).toBeInTheDocument();
  });

  it('renders operator summary and folds raw diagnostics metadata by default', () => {
    renderMemorySection(buildDetails(buildCollector({ name: 'ok.collector' })));

    expect(screen.getByText('현재 상태')).toBeInTheDocument();
    expect(screen.getByText('최근 샘플 기준 특이 증가 신호가 없습니다.')).toBeInTheDocument();
    expect(screen.getByText('상세 진단 정보')).toBeInTheDocument();
    expect(screen.getByText('리더/수집/요청 메타데이터')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '즉시 스냅샷' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'GC 전후 비교' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '내보내기' })).toBeInTheDocument();

    const rawDetails = screen.getByText('상세 진단 정보').closest('details');
    expect(rawDetails).not.toBeNull();
    expect(rawDetails).not.toHaveAttribute('open');
  });

  it('renders leak suspects as suspicion wording only when present', () => {
    renderMemorySection(
      buildDetails(buildCollector({ name: 'ok.collector' }), [
        {
          name: 'process.rss_bytes',
          source: 'process',
          classification: 'leak_suspect',
          slope_bytes_per_min: 64 * 1024 * 1024,
          monotonic_ratio: 1,
          baseline_bytes: 100 * 1024 * 1024,
          latest_bytes: 180 * 1024 * 1024,
          increase_ratio: 1.8,
          sample_count: 4,
          budget: { warn_growth_per_min: 32 * 1024 * 1024 },
        },
      ])
    );

    expect(screen.getAllByText('누수 의심').length).toBeGreaterThan(0);
    expect(screen.getByText('process.rss_bytes')).toBeInTheDocument();
    expect(screen.getByText('의심')).toBeInTheDocument();
    expect(screen.queryByText('확정')).not.toBeInTheDocument();
  });
  it('renders GC delta when a manual snapshot is present and invokes the GC action', () => {
    const onGc = vi.fn();
    renderMemorySection(
      buildDetails(
        buildCollector({ name: 'ok.collector' }),
        [],
        {
          captured_at: '2026-06-27T17:30:00+00:00',
          latency_ms: 12.5,
          collected: { gen0: 1, gen1: 2, gen2: 3, total: 6 },
          before: { rss_bytes: 100 * 1024 * 1024 },
          after: { rss_bytes: 120 * 1024 * 1024 },
          delta: {
            rss_bytes: 20 * 1024 * 1024,
            uss_bytes: -4 * 1024 * 1024,
            private_bytes: null,
          },
        }
      ),
      { onGc }
    );

    fireEvent.click(screen.getByRole('button', { name: /GC/ }));

    expect(onGc).toHaveBeenCalledOnce();
    expect(screen.getByText('12.5 ms')).toBeInTheDocument();
    expect(screen.getByText('+20.0 MB')).toBeInTheDocument();
    expect(screen.getByText('-4.0 MB')).toBeInTheDocument();
  });

  it('renders exactness badges for observed, enumerated estimate, and unavailable collectors', () => {
    renderMemorySection(
      buildDetails([
        buildCollector({ name: 'observed.heap', exactness: 'observed', bytes: 4 * 1024 * 1024 }),
        buildCollector({
          name: 'enumerated.storage',
          exactness: 'estimated-enumerated',
          bytes: 1024,
        }),
        buildCollector({ name: 'missing.heap', exactness: 'unavailable', bytes: 0 }),
      ])
    );

    expect(screen.getByText('observed.heap')).toBeInTheDocument();
    expect(screen.getByText('observed')).toBeInTheDocument();
    expect(screen.getByText('estimated-enumerated')).toBeInTheDocument();
    expect(screen.getAllByText('unavailable').length).toBeGreaterThan(0);
  });

  it('renders Electron process metrics when the bridge returns a snapshot', () => {
    const frontendMemory: FrontendMemorySnapshot = {
      captured_at: 1790000000,
      support: { mode: 'unsupported', supported: false, exactness: 'unavailable' },
      electron: {
        supported: true,
        source: 'electron',
        captured_at: 1790000000,
        process: { privateBytes: 1024, workingSetSize: 4096 },
        metrics: [
          {
            pid: 123,
            type: 'renderer',
            memory: { privateBytes: 2048, workingSetSize: 4096 },
            cpu: { percentCPUUsage: 1.5 },
          },
        ],
        v8_heap: {
          used_heap_size: 16 * 1024 * 1024,
          heap_size_limit: 64 * 1024 * 1024,
        },
        error: null,
      },
      top_consumers: [],
      growth: [],
      alerts: [],
      last_refresh_at: 1790000000000,
      history: [],
    };

    renderMemorySection(buildDetails(buildCollector({ name: 'ok.collector' })), { frontendMemory });

    expect(screen.getByText('Electron Processes')).toBeInTheDocument();
    expect(screen.getByText('ELECTRON')).toBeInTheDocument();
    expect(screen.getByText(/renderer 123: 2\.0 MB/)).toBeInTheDocument();
    expect(screen.getByText(/CPU 1\.50%/)).toBeInTheDocument();
  });
});
