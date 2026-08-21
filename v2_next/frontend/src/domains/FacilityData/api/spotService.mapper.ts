const SPOT_OPERATOR_IMAGE_PATH = '/api/spot/live_image.jpg';
const SPOT_SNAPSHOT_IMAGE_PATH = '/api/spot/image.jpg';

export const buildSpotImageUrl = (
  apiBase: string,
  configuredPath: string = SPOT_OPERATOR_IMAGE_PATH
): string => {
  const imagePath = configuredPath === SPOT_SNAPSHOT_IMAGE_PATH
    ? SPOT_SNAPSHOT_IMAGE_PATH
    : SPOT_OPERATOR_IMAGE_PATH;
  return `${apiBase}${imagePath}`;
};
