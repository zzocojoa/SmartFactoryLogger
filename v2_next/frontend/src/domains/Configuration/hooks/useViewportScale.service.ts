export const applyRowHeightToCSS = (rowHeight: number): void => {
  document.documentElement.style.setProperty('--grid-row-height', `${rowHeight}px`);
};
