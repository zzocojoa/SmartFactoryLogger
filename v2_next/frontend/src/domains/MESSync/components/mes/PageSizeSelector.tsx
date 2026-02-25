import React from 'react';
import { PageSizeSelectorView } from './components/PageSizeSelector.view';
import { usePageSizeSelectorModel } from './hooks/usePageSizeSelectorModel';
import type { PageSizeSelectorProps } from './types/PageSizeSelector.types';

export const PageSizeSelector: React.FC<PageSizeSelectorProps> = (props) => {
  const model = usePageSizeSelectorModel(props);
  return <PageSizeSelectorView {...props} model={model} />;
};
