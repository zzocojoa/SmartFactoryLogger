import React from 'react';
import { CustomDialogView } from './components/CustomDialog.view';
import { useCustomDialogModel } from './hooks/useCustomDialogModel';

export const CustomDialog: React.FC = () => {
  const model = useCustomDialogModel();

  if (!model.isOpen) {
    return null;
  }

  return <CustomDialogView model={model} />;
};
