import {
  setBackendSrv,
  setLocationSrv,
  BackendSrv,
  BackendSrvRequest,
} from '@grafana/runtime';
import { locationService } from '@grafana/runtime';

/**
 * Mocks the necessary Grafana services to allow @grafana/scenes to run
 * in a standalone React application.
 */
export function initScenesRuntime() {
  if (!(window as any).grafanaBootData) {
    (window as any).grafanaBootData = {
      settings: {},
      user: {},
      navTree: [],
    };
  }

  // 1. Mock BackendSrv (The API layer)
  // Since we use Axios in App.tsx, we can either bridge it or minimal mock it.
  // Scenes mostly uses it for data querying, but if we use custom React objects,
  // we might not touch this much yet.
  const mockBackendSrv: Partial<BackendSrv> = {
    datasourceRequest: (options: BackendSrvRequest) => {
      return Promise.resolve({ data: [], status: 200, statusText: 'OK' });
    },
    // Add other methods if Scenes internals crash calling them
  } as any;

  setBackendSrv(mockBackendSrv as BackendSrv);

  // 2. Mock LocationSrv (The Navigation layer)
  // This is critical for Scenes to handle URL states (variables, time ranges)
  setLocationSrv(locationService);
}
