export const resolveAspectRatioLabel = (viewportWidth: number, viewportHeight: number): string => {
  const ratio = viewportWidth / viewportHeight;
  if (ratio >= 2.2) {
    return '21:9';
  }
  if (ratio >= 1.6) {
    return '16:9';
  }
  if (ratio >= 1.2) {
    return '4:3';
  }
  return 'portrait';
};

export const resolveRowHeight = (
  viewportHeight: number,
  baseViewportHeight: number,
  defaultRowHeight: number,
  minRowHeight: number,
  maxRowHeight: number
): { rowHeight: number; scaleFactor: number } => {
  const scaleFactor = viewportHeight / baseViewportHeight;
  const rawRowHeight = defaultRowHeight * scaleFactor;
  const rowHeight = Math.max(minRowHeight, Math.min(maxRowHeight, Math.round(rawRowHeight)));
  return { rowHeight, scaleFactor };
};
