export interface GrafanaEmbedProps {
  dashboardUrl: string;
  height?: string | number;
  title?: string;
}

export interface GrafanaEmbedModel {
  isLoading: boolean;
  hasError: boolean;
  resolvedHeight: string;
  hasDashboardUrl: boolean;
  handleLoad: () => void;
  handleError: () => void;
}

export interface GrafanaEmbedViewProps extends GrafanaEmbedProps {
  model: GrafanaEmbedModel;
}
