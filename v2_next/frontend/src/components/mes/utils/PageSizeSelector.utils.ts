import type React from 'react';

export const DEFAULT_PAGE_SIZE_OPTIONS = [50, 100, 200] as const;

export const selectorContainerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
};

export const selectorLabelStyle: React.CSSProperties = {
  fontSize: '0.85rem',
  color: 'var(--text-secondary)',
};

export const selectorDropdownWrapperStyle: React.CSSProperties = {
  position: 'relative',
};

export const selectorTriggerButtonStyle: React.CSSProperties = {
  padding: '6px 12px',
  borderRadius: '4px',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-secondary)',
  color: 'var(--text-primary)',
  fontSize: '0.85rem',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  minWidth: '80px',
  justifyContent: 'space-between',
  transition: 'all 0.2s',
};

export const selectorDropdownMenuStyle: React.CSSProperties = {
  position: 'absolute',
  top: '100%',
  left: 0,
  right: 0,
  marginTop: '4px',
  background: '#242731',
  border: '1px solid var(--border-color)',
  borderRadius: '4px',
  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.5)',
  zIndex: 50,
  overflow: 'hidden',
};

export const createDropdownOptionStyle = (isSelected: boolean): React.CSSProperties => ({
  padding: '8px 12px',
  cursor: 'pointer',
  fontSize: '0.85rem',
  color: 'var(--text-primary)',
  background: isSelected ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
  transition: 'background 0.2s',
});

export const normalizePageSizeOptions = (options?: number[]): number[] =>
  options && options.length > 0 ? options : [...DEFAULT_PAGE_SIZE_OPTIONS];

export const isClickOutsideDropdown = (
  dropdownElement: HTMLDivElement | null,
  eventTarget: EventTarget | null
): boolean => {
  if (!dropdownElement || !eventTarget) {
    return false;
  }

  return !dropdownElement.contains(eventTarget as Node);
};

export const setTriggerHoverStyle = (
  event: React.MouseEvent<HTMLButtonElement>,
  isHovered: boolean
) => {
  event.currentTarget.style.borderColor = isHovered
    ? 'var(--accent-main)'
    : 'var(--border-color)';
};

export const setOptionHoverStyle = (
  event: React.MouseEvent<HTMLDivElement>,
  isHovered: boolean,
  isSelected: boolean
) => {
  if (isSelected) {
    return;
  }

  event.currentTarget.style.background = isHovered
    ? 'var(--bg-hover)'
    : 'transparent';
};
