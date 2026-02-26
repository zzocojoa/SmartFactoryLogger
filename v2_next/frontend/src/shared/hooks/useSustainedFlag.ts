/**
 * 조건이 일정 시간 이상 지속될 때 활성화되는 플래그 훅
 */
import { useEffect, useRef, useState } from 'react';

export const useSustainedFlag = (condition: boolean, durationMs: number) => {
  const [active, setActive] = useState(false);
  const sinceRef = useRef<number | null>(null);

  useEffect(() => {
    const now = Date.now();
    if (condition) {
      if (sinceRef.current === null) {
        sinceRef.current = now;
      }
      if (!active && now - sinceRef.current >= durationMs) {
        setActive(true);
      }
    } else {
      sinceRef.current = null;
      if (active) {
        setActive(false);
      }
    }
  }, [condition, durationMs, active]);

  return active;
};
