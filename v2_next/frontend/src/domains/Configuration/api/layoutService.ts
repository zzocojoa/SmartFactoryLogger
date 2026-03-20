import { LOCAL_LAYOUT_STORAGE_KEY, STORAGE_MODE_KEY, type StorageMode } from '../../../shared/constants/logic';
import type { LayoutMap, LayoutSnapshot } from '../../../shared/types';
import {
  buildClientLayoutPayload,
  generateUUIDv4,
  resolveStorageMode,
} from './layoutService.mapper';
import type { LayoutSavePayload } from './layoutService.types';
import { safeGetItem, safeSetItem } from '../../../shared/utils/safeStorage';
import {
  deleteClientLayoutSlot,
  fetchClientLatestLayout,
  fetchClientLayoutList,
  fetchClientLayoutSlot,
  fetchLayouts,
  fetchLayoutSnapshot,
  postClientLayout,
  postDeleteLayout,
  postRestoreLayout,
  postSaveLayout,
} from '../../../shared/api/transport/layoutService.transport';

const CLIENT_ID_KEY = 'sfl_client_id';

function getClientId(): string {
  let clientId = safeGetItem(CLIENT_ID_KEY);
  if (!clientId) {
    clientId = generateUUIDv4();
    safeSetItem(CLIENT_ID_KEY, clientId);
    console.log(`[ClientLayout] Generated new client ID: ${clientId}`);
  }
  return clientId;
}

export const layoutService = {
  getLayouts: fetchLayouts,

  saveLayout: (payload: LayoutSavePayload) => postSaveLayout(payload),

  getLayoutSnapshot: fetchLayoutSnapshot,

  restoreLayout: (slotId: string) => postRestoreLayout({ slot_id: slotId }),

  deleteLayout: (slotId: string) => postDeleteLayout({ slot_id: slotId }),
};

export const localLayoutService = {
  getClientId,

  getLocalLayout: async (): Promise<LayoutSnapshot | null> => {
    try {
      const clientId = getClientId();
      return await fetchClientLatestLayout(clientId);
    } catch (e: any) {
      if (e?.response?.status === 404) {
        return null;
      }
      console.error('Failed to load client layout', e);
      return null;
    }
  },

  getLayoutList: async (): Promise<any[]> => {
    try {
      const clientId = getClientId();
      return await fetchClientLayoutList(clientId);
    } catch (e) {
      console.error('Failed to list client layouts', e);
      return [];
    }
  },

  restoreLocalLayout: async (slotId: string): Promise<LayoutSnapshot | null> => {
    try {
      const clientId = getClientId();
      return await fetchClientLayoutSlot(clientId, slotId);
    } catch (e) {
      console.error('Failed to restore client layout slot', e);
      throw e;
    }
  },

  saveLocalLayout: async (layout: LayoutMap, name: string, cols: number = 60): Promise<boolean> => {
    try {
      const clientId = getClientId();
      const payload = buildClientLayoutPayload(layout, name, cols);
      await postClientLayout(clientId, payload);
      console.log(`[ClientLayout] Saved layout '${name}' for client: ${clientId}`);
      return true;
    } catch (e) {
      console.error('Failed to save client layout', e);
      return false;
    }
  },

  deleteLocalLayout: async (slotId: string): Promise<void> => {
    try {
      const clientId = getClientId();
      await deleteClientLayoutSlot(clientId, slotId);
      console.log(`[ClientLayout] Deleted layout '${slotId}'`);
    } catch (e) {
      console.error('Failed to delete client layout', e);
      throw e;
    }
  },

  hasLocalLayout: async (): Promise<boolean> => {
    try {
      const clientId = getClientId();
      await fetchClientLatestLayout(clientId);
      return true;
    } catch (e: any) {
      if (e?.response?.status === 404) {
        return false;
      }
      return false;
    }
  },

  getStorageMode: (): StorageMode => {
    const mode = safeGetItem(STORAGE_MODE_KEY);
    return resolveStorageMode(mode);
  },

  setStorageMode: (mode: StorageMode): void => {
    safeSetItem(STORAGE_MODE_KEY, mode);
    console.log(`[ClientLayout] Storage mode set to: ${mode}`);
  },
};

// Keep the key exported for backward compatibility with existing storage migration logic.
export { LOCAL_LAYOUT_STORAGE_KEY };
