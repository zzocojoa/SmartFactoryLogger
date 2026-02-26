import React from 'react';
import ChevronDown from 'lucide-react/dist/esm/icons/chevron-down';
import ChevronUp from 'lucide-react/dist/esm/icons/chevron-up';
import type { PageSizeSelectorViewProps } from '../types/PageSizeSelector.types';
import {
  createDropdownOptionStyle,
  selectorContainerStyle,
  selectorDropdownMenuStyle,
  selectorDropdownWrapperStyle,
  selectorLabelStyle,
  selectorTriggerButtonStyle,
} from '../utils/PageSizeSelector.utils';

export const PageSizeSelectorView: React.FC<PageSizeSelectorViewProps> = ({
  pageSize,
  model,
}) => {
  const {
    isOpen,
    dropdownRef,
    resolvedOptions,
    toggleOpen,
    handleSelect,
    handleTriggerMouseEnter,
    handleTriggerMouseLeave,
    handleOptionMouseEnter,
    handleOptionMouseLeave,
  } = model;

  return (
    <div style={selectorContainerStyle}>
      <span style={selectorLabelStyle}>표시:</span>

      <div ref={dropdownRef} style={selectorDropdownWrapperStyle}>
        <button
          onClick={toggleOpen}
          style={selectorTriggerButtonStyle}
          onMouseEnter={handleTriggerMouseEnter}
          onMouseLeave={handleTriggerMouseLeave}
        >
          {pageSize}건
          {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        {isOpen && (
          <div style={selectorDropdownMenuStyle}>
            {resolvedOptions.map((option) => {
              const isSelected = pageSize === option;

              return (
                <div
                  key={option}
                  onClick={() => handleSelect(option)}
                  style={createDropdownOptionStyle(isSelected)}
                  onMouseEnter={(event) => handleOptionMouseEnter(event, isSelected)}
                  onMouseLeave={(event) => handleOptionMouseLeave(event, isSelected)}
                >
                  {option}건
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
