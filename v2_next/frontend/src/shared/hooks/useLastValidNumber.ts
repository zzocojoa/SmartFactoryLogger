/**
 * 마지막 유효 숫자값 유지 훅
 */
import { useEffect, useRef } from 'react';

export const useLastValidNumber = (value: number | null | undefined) => {
  const lastRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      lastRef.current = value;
    }
  }, [value]);

  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  return lastRef.current;
};
