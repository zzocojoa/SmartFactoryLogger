import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import type {
  PageSizeSelectorModel,
  PageSizeSelectorProps,
} from '../types/PageSizeSelector.types';
import {
  isClickOutsideDropdown,
  normalizePageSizeOptions,
  setOptionHoverStyle,
  setTriggerHoverStyle,
} from '../utils/PageSizeSelector.utils';

export const usePageSizeSelectorModel = ({
  onPageSizeChange,
  options,
}: PageSizeSelectorProps): PageSizeSelectorModel => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const resolvedOptions = useMemo(() => normalizePageSizeOptions(options), [options]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (isClickOutsideDropdown(dropdownRef.current, event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const toggleOpen = useCallback(() => {
    setIsOpen((prev) => !prev);
  }, []);

  const handleSelect = useCallback(
    (size: number) => {
      onPageSizeChange(size);
      setIsOpen(false);
    },
    [onPageSizeChange]
  );

  const handleTriggerMouseEnter = useCallback((event: ReactMouseEvent<HTMLButtonElement>) => {
    setTriggerHoverStyle(event, true);
  }, []);

  const handleTriggerMouseLeave = useCallback((event: ReactMouseEvent<HTMLButtonElement>) => {
    setTriggerHoverStyle(event, false);
  }, []);

  const handleOptionMouseEnter = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>, isSelected: boolean) => {
      setOptionHoverStyle(event, true, isSelected);
    },
    []
  );

  const handleOptionMouseLeave = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>, isSelected: boolean) => {
      setOptionHoverStyle(event, false, isSelected);
    },
    []
  );

  return {
    isOpen,
    dropdownRef,
    resolvedOptions,
    toggleOpen,
    handleSelect,
    handleTriggerMouseEnter,
    handleTriggerMouseLeave,
    handleOptionMouseEnter,
    handleOptionMouseLeave,
  };
};
