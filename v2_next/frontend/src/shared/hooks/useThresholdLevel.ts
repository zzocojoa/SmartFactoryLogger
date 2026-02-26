/**
 * 임계값 수준(normal/warn/danger)을 추적하는 훅
 */
import { useEffect, useRef, useState } from 'react';
import type { ThresholdLevel } from '../utils/thresholds';

export { type ThresholdLevel };

export const useThresholdLevel = (value: number, warnThreshold: number, dangerThreshold: number, holdMs: number) => {
  const [level, setLevel] = useState<ThresholdLevel>('normal');
  const warnSinceRef = useRef<number | null>(null);
  const dangerSinceRef = useRef<number | null>(null);

  useEffect(() => {
    if (!Number.isFinite(value)) {
      warnSinceRef.current = null;
      dangerSinceRef.current = null;
      return;
    }

    const now = Date.now();

    if (value >= dangerThreshold) {
      if (dangerSinceRef.current === null) {
        dangerSinceRef.current = now;
      }
      warnSinceRef.current = null;
      if (now - dangerSinceRef.current >= holdMs && level !== 'danger') {
        setLevel('danger');
      }
      return;
    }

    dangerSinceRef.current = null;

    if (value >= warnThreshold) {
      if (warnSinceRef.current === null) {
        warnSinceRef.current = now;
      }
      if (level === 'danger') {
        setLevel('warn');
      }
      if (now - warnSinceRef.current >= holdMs && level !== 'warn') {
        setLevel('warn');
      }
      return;
    }

    warnSinceRef.current = null;
    if (level !== 'normal') {
      setLevel('normal');
    }
  }, [value, warnThreshold, dangerThreshold, holdMs, level]);

  return level;
};
