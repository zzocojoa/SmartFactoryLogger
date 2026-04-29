import type { LayoutEntry } from '../../../shared/types';

export interface LayoutEditContextValue {
  isEditing: boolean;
  deleteWidget: (key: string) => void;
  updateWidget: (key: string, updates: Partial<LayoutEntry>) => void;
}
