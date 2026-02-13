import { useCallback, useState } from 'react';
import type { GrafanaEmbedModel, GrafanaEmbedProps } from '../types/GrafanaEmbed.types';
import { resolveEmbedHeight } from '../utils/GrafanaEmbed.utils';

export const useGrafanaEmbedModel = ({ dashboardUrl, height = '100%' }: GrafanaEmbedProps): GrafanaEmbedModel => {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  const handleLoad = useCallback(() => {
    setIsLoading(false);
  }, []);

  const handleError = useCallback(() => {
    setIsLoading(false);
    setHasError(true);
  }, []);

  return {
    isLoading,
    hasError,
    resolvedHeight: resolveEmbedHeight(height),
    hasDashboardUrl: Boolean(dashboardUrl),
    handleLoad,
    handleError,
  };
};
