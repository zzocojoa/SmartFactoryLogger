import React from 'react';
import { DataGridToolbarView } from './components/DataGridToolbar.view';
import { useDataGridToolbarModel } from './hooks/useDataGridToolbarModel';
import type { DataGridToolbarProps } from './types/DataGridToolbar.types';

export const DataGridToolbar: React.FC<DataGridToolbarProps> = (props) => {
  const model = useDataGridToolbarModel(props);
  return <DataGridToolbarView {...props} model={model} />;
};
