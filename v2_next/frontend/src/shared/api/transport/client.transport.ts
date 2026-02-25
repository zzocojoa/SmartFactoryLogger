import type { RuntimeLikeLocation } from '../client.types';

export const getRuntimeLocation = (): RuntimeLikeLocation => {
  // eslint-disable-next-line no-restricted-globals
  return (typeof window !== 'undefined' ? window.location : self.location) as RuntimeLikeLocation;
};
