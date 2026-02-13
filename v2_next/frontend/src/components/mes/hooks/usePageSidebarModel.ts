import { useCallback, useEffect, useMemo, useState } from 'react';
import type { PageSidebarModel, PageSidebarProps } from '../types/PageSidebar.types';
import {
  getCategoryKeys,
  groupPagesByCategory,
  loadExpandedCategories,
  saveExpandedCategories,
  toggleExpandedCategory,
} from '../utils/PageSidebar.utils';

export const usePageSidebarModel = ({ pageItems }: PageSidebarProps): PageSidebarModel => {
  const groupedPages = useMemo(() => groupPagesByCategory(pageItems), [pageItems]);
  const categoryKeys = useMemo(() => getCategoryKeys(pageItems), [pageItems]);

  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(() =>
    loadExpandedCategories()
  );

  useEffect(() => {
    saveExpandedCategories(expandedCategories);
  }, [expandedCategories]);

  const toggleCategory = useCallback((category: string) => {
    setExpandedCategories((prev) => toggleExpandedCategory(prev, category));
  }, []);

  return {
    groupedPages,
    categoryKeys,
    expandedCategories,
    toggleCategory,
  };
};
