import type React from 'react';

export interface PageSizeSelectorProps {
  pageSize: number;
  onPageSizeChange: (size: number) => void;
  options?: number[];
}

export interface PageSizeSelectorModel {
  isOpen: boolean;
  dropdownRef: React.RefObject<HTMLDivElement>;
  resolvedOptions: number[];
  toggleOpen: () => void;
  handleSelect: (size: number) => void;
  handleTriggerMouseEnter: (event: React.MouseEvent<HTMLButtonElement>) => void;
  handleTriggerMouseLeave: (event: React.MouseEvent<HTMLButtonElement>) => void;
  handleOptionMouseEnter: (event: React.MouseEvent<HTMLDivElement>, isSelected: boolean) => void;
  handleOptionMouseLeave: (event: React.MouseEvent<HTMLDivElement>, isSelected: boolean) => void;
}

export interface PageSizeSelectorViewProps extends PageSizeSelectorProps {
  model: PageSizeSelectorModel;
}
