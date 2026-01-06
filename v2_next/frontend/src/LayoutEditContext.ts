import React from 'react';

export const LayoutEditContext = React.createContext<{ isEditing: boolean; deleteWidget: (key: string) => void; updateWidget: (key: string, updates: any) => void }>({ isEditing: false, deleteWidget: () => {}, updateWidget: () => {} });
