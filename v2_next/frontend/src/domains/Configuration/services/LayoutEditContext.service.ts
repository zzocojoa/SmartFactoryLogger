import type { LayoutEditContextValue } from '../types/LayoutEditContext.types';

export const buildDefaultLayoutEditContextValue = (): LayoutEditContextValue => ({
  isEditing: false,
  deleteWidget: () => {},
  updateWidget: () => {},
});
