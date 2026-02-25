import type React from 'react';
import type { PageItem } from '../types/PageSidebar.types';

export const SIDEBAR_EXPANDED_STORAGE_KEY = 'mes_sidebar_expanded_categories';

export const groupPagesByCategory = (pageItems: PageItem[]): Record<string, PageItem[]> => {
  return pageItems.reduce<Record<string, PageItem[]>>((groups, pageItem) => {
    if (!groups[pageItem.category]) {
      groups[pageItem.category] = [];
    }
    groups[pageItem.category].push(pageItem);
    return groups;
  }, {});
};

export const getCategoryKeys = (pageItems: PageItem[]): string[] => {
  const categorySet = new Set(pageItems.map((pageItem) => pageItem.category));
  return Array.from(categorySet);
};

export const loadExpandedCategories = (): Set<string> => {
  try {
    const raw = localStorage.getItem(SIDEBAR_EXPANDED_STORAGE_KEY);
    if (raw) {
      return new Set(JSON.parse(raw));
    }
  } catch {
    // Ignore localStorage parse/access errors.
  }
  return new Set();
};

export const saveExpandedCategories = (expandedCategories: Set<string>) => {
  try {
    localStorage.setItem(
      SIDEBAR_EXPANDED_STORAGE_KEY,
      JSON.stringify(Array.from(expandedCategories))
    );
  } catch {
    // Ignore localStorage write errors.
  }
};

export const toggleExpandedCategory = (
  expandedCategories: Set<string>,
  category: string
): Set<string> => {
  const next = new Set(expandedCategories);
  if (next.has(category)) {
    next.delete(category);
  } else {
    next.add(category);
  }
  return next;
};

export const createSidebarRootStyle = (isOpen: boolean): React.CSSProperties => ({
  width: isOpen ? '250px' : '0px',
  background: 'var(--bg-secondary)',
  borderRight: '1px solid var(--border-color)',
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
  overflow: 'hidden',
  whiteSpace: 'nowrap',
  willChange: 'width',
  position: 'relative',
});

export const createSidebarSectionStyle = (
  isOpen: boolean,
  extra: React.CSSProperties = {}
): React.CSSProperties => ({
  opacity: isOpen ? 1 : 0,
  transition: 'opacity 0.2s',
  transitionDelay: isOpen ? '0.1s' : '0s',
  ...extra,
});

export const createCategoryHeaderStyle = (): React.CSSProperties => ({
  color: 'var(--accent-main)',
  fontSize: '0.85rem',
  fontWeight: 'bold',
  textTransform: 'uppercase',
  marginBottom: '0.5rem',
  padding: '0.5rem',
  borderLeft: '2px solid var(--accent-main)',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  userSelect: 'none',
  background: 'transparent',
  transition: 'background 0.2s',
});

export const createCategoryContentStyle = (isExpanded: boolean): React.CSSProperties => ({
  maxHeight: isExpanded ? '500px' : '0px',
  overflow: 'hidden',
  transition: 'max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s',
  opacity: isExpanded ? 1 : 0,
});

export const sidebarHeaderTitleStyle: React.CSSProperties = {
  margin: 0,
  color: 'var(--text-primary)',
  fontSize: '1.1rem',
};

export const sidebarLoadingTextStyle: React.CSSProperties = {
  color: 'var(--text-secondary)',
};

export const sidebarErrorTextStyle: React.CSSProperties = {
  color: 'var(--state-danger)',
};

export const sidebarEmptyTextStyle: React.CSSProperties = {
  color: 'var(--text-secondary)',
  fontSize: '0.9rem',
};

export const sidebarCategoryItemStyle: React.CSSProperties = {
  marginBottom: '0.5rem',
};

export const sidebarChevronStyle = (isExpanded: boolean): React.CSSProperties => ({
  transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
  transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
  opacity: 0.7,
});

export const sidebarListStyle: React.CSSProperties = {
  listStyle: 'none',
  padding: 0,
  margin: 0,
};

export const sidebarListItemStyle: React.CSSProperties = {
  marginBottom: '0.2rem',
};

export const createPageButtonStyle = (isSelected: boolean): React.CSSProperties => ({
  width: '100%',
  textAlign: 'left',
  padding: '8px 15px',
  background: isSelected ? 'rgba(74, 222, 128, 0.1)' : 'transparent',
  color: isSelected ? 'var(--accent-main)' : 'var(--text-secondary)',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  transition: 'all 0.2s',
  fontWeight: isSelected ? 600 : 400,
  fontSize: '0.9rem',
  display: 'flex',
  alignItems: 'center',
  paddingLeft: '1.5rem',
});

export const sidebarPageBulletStyle: React.CSSProperties = {
  marginRight: '8px',
  opacity: 0.7,
};
