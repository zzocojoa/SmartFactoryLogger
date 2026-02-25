import React from 'react';
import { GrafanaEmbedView } from './components/GrafanaEmbed.view';
import { useGrafanaEmbedModel } from './hooks/useGrafanaEmbedModel';
import type { GrafanaEmbedProps } from './types/GrafanaEmbed.types';

export const GrafanaEmbed: React.FC<GrafanaEmbedProps> = (props) => {
  const model = useGrafanaEmbedModel(props);
  return <GrafanaEmbedView {...props} model={model} />;
};

export default GrafanaEmbed;
