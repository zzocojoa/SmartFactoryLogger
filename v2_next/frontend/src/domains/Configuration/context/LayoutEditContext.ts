import React from 'react';
import { buildDefaultLayoutEditContextValue } from '../services/LayoutEditContext.service';
import type { LayoutEditContextValue } from '../types/LayoutEditContext.types';

export const LayoutEditContext = React.createContext<LayoutEditContextValue>(
  buildDefaultLayoutEditContextValue()
);
