import { spotService } from '../api/spotService';

export const fetchSpotConfig = () => spotService.getConfig();

export const controlSpotAction = (action: string, value?: number) =>
  spotService.control({ action, value });

export const controlSpotFocus = (steps: number) => spotService.focus(steps);

export const controlSpotActuator = (step: number) => spotService.actuator(step);

export const fetchSpotImageResponse = async (): Promise<Response> => {
  const url = `${spotService.getImageUrl()}?t=${Date.now()}`;
  return fetch(url, { cache: 'no-store' });
};
