import { apiClient } from './client';

export const spotService = {
  getImageUrl: () => {
    // This returns the URL string, not the image data itself, usually.
    // Based on App.tsx usage, it might be constructed or fetched.
    // If App.tsx does: axios.get('/api/spot/image'), then:
    return '/api/spot/image'; 
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
