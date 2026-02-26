/**
 * SVG 스파크라인 경로 생성 유틸리티
 */

export const clampNumber = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export const buildSparklinePaths = (
  values: number[],
  width: number,
  height: number,
  thresholds: number[] = [],
  domain?: { min?: number; max?: number }
) => {
  if (values.length === 0) {
    return {
      linePath: '',
      areaPath: '',
      points: [] as Array<{ x: number; y: number }>,
      thresholdLines: [] as Array<{ y: number; value: number }>,
    };
  }
  const min = Number.isFinite(domain?.min)
    ? Math.min(domain?.min as number, ...values)
    : Math.min(...values);
  const max = Number.isFinite(domain?.max)
    ? Math.max(domain?.max as number, ...values)
    : Math.max(...values);
  const range = Math.max(max - min, 1);
  const lastIndex = Math.max(values.length - 1, 1);
  const points = values.map((value, index) => {
    const x = (index / lastIndex) * width;
    const y = height - ((value - min) / range) * height;
    return { x, y };
  });
  const linePath = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(' ');
  const areaPath = `${linePath} L${width.toFixed(2)},${height.toFixed(2)} L0,${height.toFixed(2)} Z`;
  const thresholdLines = thresholds
    .filter((value) => Number.isFinite(value))
    .map((value) => {
      const clamped = clampNumber(value, min, max);
      const y = height - ((clamped - min) / range) * height;
      return { y, value };
    });
  return { linePath, areaPath, points, thresholdLines };
};

export const calcPercent = (value: number, max: number) => {
  if (!Number.isFinite(value) || max <= 0) {
    return 0;
  }
  return Math.round((clampNumber(value, 0, max) / max) * 100);
};
