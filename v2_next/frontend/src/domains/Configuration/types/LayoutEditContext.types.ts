export interface LayoutEditContextValue {
  isEditing: boolean;
  deleteWidget: (key: string) => void;
  updateWidget: (key: string, updates: unknown) => void;
}
