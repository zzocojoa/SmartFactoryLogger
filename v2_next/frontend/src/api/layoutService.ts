import { apiClient } from './client';
import { LOCAL_LAYOUT_STORAGE_KEY, STORAGE_MODE_KEY, StorageMode } from '../constants/logic';
import { LayoutSnapshot, LayoutMap } from '../types';

// Client UUID storage key
const CLIENT_ID_KEY = 'sfl_client_id';

// Generate a UUID v4
function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// Get or create client UUID
function getClientId(): string {
  let clientId = localStorage.getItem(CLIENT_ID_KEY);
  if (!clientId) {
    clientId = generateUUID();
    localStorage.setItem(CLIENT_ID_KEY, clientId);
    console.log(`[ClientLayout] Generated new client ID: ${clientId}`);
  }
  return clientId;
}

// Server-based layout service (existing - shared layouts)
export const layoutService = {
  getLayouts: async () => {
    const response = await apiClient.get('/api/layouts');
    return response.data;
  },
  
  saveLayout: async (payload: any) => {
    const response = await apiClient.post('/api/layouts', payload);
    return response.data;
  },

  getLayoutSnapshot: async () => {
    const response = await apiClient.get('/api/layout');
    return response.data;
  },

  restoreLayout: async (slotId: string) => {
    const response = await apiClient.post('/api/layouts/restore', { slot_id: slotId });
    return response.data;
  },

  deleteLayout: async (slotId: string) => {
    const response = await apiClient.post('/api/layouts/delete', { slot_id: slotId });
    return response.data;
  }
};

// Client-specific layout service (uses backend API with UUID)
export const localLayoutService = {
  // Get client ID (generates one if not exists)
  getClientId,

  // Get latest active layout for auto-restore
  getLocalLayout: async (): Promise<LayoutSnapshot | null> => {
    try {
      const clientId = getClientId();
      const response = await apiClient.get(`/api/layouts/client/${clientId}/latest`);
      return response.data as LayoutSnapshot;
    } catch (e: any) {
      if (e?.response?.status === 404) {
        return null; // No active layout
      }
      console.error('Failed to load client layout', e);
      return null;
    }
  },

  // Get list of saved layouts for this client
  getLayoutList: async (): Promise<any[]> => {
    try {
      const clientId = getClientId();
      const response = await apiClient.get(`/api/layouts/client/${clientId}/list`);
      return response.data;
    } catch (e) {
      console.error('Failed to list client layouts', e);
      return [];
    }
  },

  // Restore specific layout slot
  restoreLocalLayout: async (slotId: string): Promise<LayoutSnapshot | null> => {
    try {
      const clientId = getClientId();
      const response = await apiClient.get(`/api/layouts/client/${clientId}/${slotId}`);
      return response.data as LayoutSnapshot;
    } catch (e) {
      console.error('Failed to restore client layout slot', e);
      throw e;
    }
  },

  // Save layout to server for this client (new slot)
  saveLocalLayout: async (layout: LayoutMap, name: string, cols: number = 60): Promise<boolean> => {
    try {
      const clientId = getClientId();
      const payload = {
        layout,
        cols,
        version: 'v2',
        name,
      };
      await apiClient.post(`/api/layouts/client/${clientId}`, payload);
      console.log(`[ClientLayout] Saved layout '${name}' for client: ${clientId}`);
      return true;
    } catch (e) {
      console.error('Failed to save client layout', e);
      return false;
    }
  },

  // Delete layout slot from server for this client
  deleteLocalLayout: async (slotId: string): Promise<void> => {
    try {
      const clientId = getClientId();
      await apiClient.delete(`/api/layouts/client/${clientId}/${slotId}`);
      console.log(`[ClientLayout] Deleted layout '${slotId}'`);
    } catch (e) {
      console.error('Failed to delete client layout', e);
      throw e;
    }
  },

  // Check if client has a layout saved (quick check via API)
  hasLocalLayout: async (): Promise<boolean> => {
    try {
      const clientId = getClientId();
      await apiClient.get(`/api/layouts/client/${clientId}/latest`);
      return true;
    } catch (e: any) {
      if (e?.response?.status === 404) {
        return false;
      }
      return false;
    }
  },

  // Storage mode preference (still stored in localStorage for quick access)
  getStorageMode: (): StorageMode => {
    const mode = localStorage.getItem(STORAGE_MODE_KEY);
    return (mode === 'server') ? 'server' : 'local'; // Default to local
  },

  setStorageMode: (mode: StorageMode): void => {
    localStorage.setItem(STORAGE_MODE_KEY, mode);
    console.log(`[ClientLayout] Storage mode set to: ${mode}`);
  }
};

