import React from 'react';
import { DynamicDataGridView } from './components/DynamicDataGrid.view';
import { useDynamicDataGridModel } from './hooks/useDynamicDataGridModel';
import type { DynamicDataGridProps } from './types/DynamicDataGrid.types';

export const DynamicDataGrid: React.FC<DynamicDataGridProps> = (props) => {
  const model = useDynamicDataGridModel(props);
  return <DynamicDataGridView {...props} model={model} />;
};
