import type {
  OperatorMetadataResponse,
  OperatorMetadataUpdatePayload,
} from './operatorMetadataService.types';
import {
  deleteOperatorMetadata,
  fetchOperatorMetadata,
  putOperatorMetadata,
} from '../../../shared/api/transport/operatorMetadataService.transport';

export const operatorMetadataService = {
  get: async (): Promise<OperatorMetadataResponse> => fetchOperatorMetadata(),
  update: async (payload: OperatorMetadataUpdatePayload): Promise<OperatorMetadataResponse> =>
    putOperatorMetadata(payload),
  reset: async (): Promise<OperatorMetadataResponse> => deleteOperatorMetadata(),
};
