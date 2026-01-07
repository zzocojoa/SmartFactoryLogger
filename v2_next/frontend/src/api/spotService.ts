import { apiClient, API_BASE } from './client';

export const spotService = {
  getImageUrl: () => {
    // Return the full URL for the image proxy
    // App.tsx uses: ${API_BASE}/api/spot/proxy_image
    // We assume API_BASE is handled by the caller or we should return the full path if needed.
    // Since App.tsx prepends API_BASE, we should probably return the path relative to API_BASE 
    // OR return the full URL if we import API_BASE.
    // Let's import API_BASE to be self-contained.
    return `${API_BASE}/api/spot/proxy_image`; 
  },
  
  getConfig: async () => {
    const response = await apiClient.get('/api/spot/config');
    return response.data;
  },
  
  control: async (params: any) => {
    const response = await apiClient.post('/api/spot/control', params);
    return response.data;
  },

  focus: async (steps: number) => {
    // App.tsx sends null body and uses query params for steps
    const response = await apiClient.post('/api/spot/focus', null, { params: { steps } });
    return response.data;
  },
  
  actuator: async (step: number) => {
    const response = await apiClient.post('/api/spot/actuator', { step });
    return response.data;
  }
};
