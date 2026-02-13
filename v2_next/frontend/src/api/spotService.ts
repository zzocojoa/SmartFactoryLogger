import { API_BASE } from './client';
import { buildSpotImageUrl } from './spotService.mapper';
import type { SpotControlPayload } from './spotService.types';
import {
  fetchSpotConfig,
  postSpotActuator,
  postSpotControl,
  postSpotFocus,
} from './transport/spotService.transport';

export const spotService = {
  getImageUrl: () => buildSpotImageUrl(API_BASE),
  
  getConfig: fetchSpotConfig,
  
  control: (params: SpotControlPayload) => postSpotControl(params),

  focus: (steps: number) => postSpotFocus(steps),
  
  actuator: (step: number) => postSpotActuator({ step }),
};
