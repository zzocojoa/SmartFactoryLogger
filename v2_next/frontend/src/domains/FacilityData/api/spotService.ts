import { API_BASE } from '../../../shared/api/client';
import { buildSpotImageUrl } from './spotService.mapper';
import type { SpotControlPayload } from './spotService.types';
import {
  fetchSpotConfig,
  postSpotActuator,
  postSpotControl,
  postSpotFocus,
} from '../../../shared/api/transport/spotService.transport';

export const spotService = {
  getImageUrl: (configuredPath?: string) => buildSpotImageUrl(API_BASE, configuredPath),
  
  getConfig: fetchSpotConfig,
  
  control: (params: SpotControlPayload) => postSpotControl(params),

  focus: (steps: number) => postSpotFocus(steps),
  
  actuator: (step: number) => postSpotActuator({ step }),
};

