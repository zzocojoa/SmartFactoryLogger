import React, { type ReactNode } from 'react';

export interface ReactRenderProfilerSample {
  id: string;
  phase: 'mount' | 'update' | 'nested-update';
  actualDuration: number;
  baseDuration: number;
  startTime: number;
  commitTime: number;
  capturedAt: number;
}

export interface ReactRenderProfilerSummary {
  id: string;
  commits: number;
  totalActualDuration: number;
  totalBaseDuration: number;
  maxActualDuration: number;
  avgActualDuration: number;
  mountCommits: number;
  updateCommits: number;
}

export interface ReactRenderProfilerCollector {
  samples: ReactRenderProfilerSample[];
  reset: () => void;
  summarize: () => ReactRenderProfilerSummary[];
}

interface ProfilerProbeProps {
  id: string;
  children: ReactNode;
}

declare global {
  interface Window {
    __SF_REACT_PROFILER__?: ReactRenderProfilerCollector;
    __SF_REACT_PROFILER_RESET_DONE__?: boolean;
  }
}

const PROFILER_QUERY_KEY = 'sfReactProfiler';
const PROFILER_RESET_QUERY_KEY = 'sfReactProfilerReset';
const PROFILER_STORAGE_KEY = 'sf-react-profiler';

const isBrowser = (): boolean => typeof window !== 'undefined';

const isProfilerStorageEnabled = (): boolean => {
  try {
    return window.localStorage.getItem(PROFILER_STORAGE_KEY) === '1';
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === 'SecurityError') {
      return false;
    }

    throw error;
  }
};

export const isReactRenderProfilerEnabled = (): boolean => {
  if (!isBrowser()) {
    return false;
  }

  const params = new URLSearchParams(window.location.search);
  if (params.get(PROFILER_QUERY_KEY) === '1') {
    return true;
  }

  return isProfilerStorageEnabled();
};

const shouldResetProfiler = (): boolean => {
  if (!isBrowser()) {
    return false;
  }

  const params = new URLSearchParams(window.location.search);
  return params.get(PROFILER_RESET_QUERY_KEY) === '1';
};

const summarizeSamples = (samples: ReactRenderProfilerSample[]): ReactRenderProfilerSummary[] => {
  const byId = new Map<string, ReactRenderProfilerSample[]>();

  samples.forEach((sample) => {
    const current = byId.get(sample.id) ?? [];
    current.push(sample);
    byId.set(sample.id, current);
  });

  return Array.from(byId.entries())
    .map(([id, idSamples]) => {
      const commits = idSamples.length;
      const totalActualDuration = idSamples.reduce((sum, sample) => sum + sample.actualDuration, 0);
      const totalBaseDuration = idSamples.reduce((sum, sample) => sum + sample.baseDuration, 0);
      const maxActualDuration = idSamples.reduce(
        (max, sample) => Math.max(max, sample.actualDuration),
        0,
      );
      const mountCommits = idSamples.filter((sample) => sample.phase === 'mount').length;
      const updateCommits = commits - mountCommits;

      return {
        id,
        commits,
        totalActualDuration,
        totalBaseDuration,
        maxActualDuration,
        avgActualDuration: commits > 0 ? totalActualDuration / commits : 0,
        mountCommits,
        updateCommits,
      };
    })
    .sort((left, right) => left.id.localeCompare(right.id));
};

const getProfilerCollector = (): ReactRenderProfilerCollector | null => {
  if (!isBrowser() || !isReactRenderProfilerEnabled()) {
    return null;
  }

  if (!window.__SF_REACT_PROFILER__) {
    window.__SF_REACT_PROFILER__ = {
      samples: [],
      reset: () => {
        window.__SF_REACT_PROFILER__?.samples.splice(0);
      },
      summarize: () => summarizeSamples(window.__SF_REACT_PROFILER__?.samples ?? []),
    };
  }

  if (shouldResetProfiler() && !window.__SF_REACT_PROFILER_RESET_DONE__) {
    window.__SF_REACT_PROFILER__.reset();
    window.__SF_REACT_PROFILER_RESET_DONE__ = true;
  }

  return window.__SF_REACT_PROFILER__;
};

const recordRenderSample = (
  id: string,
  phase: 'mount' | 'update' | 'nested-update',
  actualDuration: number,
  baseDuration: number,
  startTime: number,
  commitTime: number,
): void => {
  const collector = getProfilerCollector();

  if (!collector) {
    return;
  }

  collector.samples.push({
    id,
    phase,
    actualDuration,
    baseDuration,
    startTime,
    commitTime,
    capturedAt: performance.now(),
  });
};

export const ProfilerProbe = ({ id, children }: ProfilerProbeProps): JSX.Element => {
  if (!isReactRenderProfilerEnabled()) {
    return <>{children}</>;
  }

  return (
    <React.Profiler id={id} onRender={recordRenderSample}>
      {children}
    </React.Profiler>
  );
};
