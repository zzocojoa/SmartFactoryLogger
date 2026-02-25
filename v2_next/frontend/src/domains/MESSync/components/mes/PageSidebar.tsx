import React from 'react';
import { PageSidebarView } from './components/PageSidebar.view';
import { usePageSidebarModel } from './hooks/usePageSidebarModel';
import type { PageSidebarProps } from './types/PageSidebar.types';

export type { PageItem } from './types/PageSidebar.types';

export const PageSidebar: React.FC<PageSidebarProps> = (props) => {
  const model = usePageSidebarModel(props);
  return <PageSidebarView {...props} model={model} />;
};
