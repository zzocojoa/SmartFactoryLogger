import { apiClient } from '../client';
import type {
  OperatorMetadataResponse,
  OperatorMetadataUpdatePayload,
} from '../../../domains/FacilityData/api/operatorMetadataService.types';

export const fetchOperatorMetadata = async (): Promise<OperatorMetadataResponse> => {
  const response = await apiClient.get<OperatorMetadataResponse>('/api/facility/operator-metadata');
  return response.data;
};

export const putOperatorMetadata = async (
  payload: OperatorMetadataUpdatePayload
): Promise<OperatorMetadataResponse> => {
  const response = await apiClient.put<OperatorMetadataResponse>('/api/facility/operator-metadata', payload);
  return response.data;
};

export const deleteOperatorMetadata = async (): Promise<OperatorMetadataResponse> => {
  const response = await apiClient.delete<OperatorMetadataResponse>('/api/facility/operator-metadata');
  return response.data;
};
