import type {
  CommLogInfo,
  ConnectionTestResponse,
  HealthSnapshot,
  ObservabilityErrorsResponse,
  PathHealthResult,
  StatsSnapshot,
} from '../types';

export interface ObservabilityExportRequest {
  include_errors: boolean;
  front_errors: Array<{
    type: string;
    message: string;
    source?: string;
    timestamp?: number;
  }>;
}

export interface LatestExportPathResponse {
  path: string | null;
}

export interface ReconnectResponse {
  ok: boolean;
}

export interface PathHealthRequestItem {
  key: string;
  path: string;
}

export type PathHealthResponse = Record<string, PathHealthResult>;

export interface BrowseFolderParams {
  initial_dir?: string;
  title?: string;
}

export interface BrowseFolderResponse {
  ok: boolean;
  path: string | null;
}

export interface CreatePathResponse {
  ok: boolean;
}

export interface SnapshotPayload {
  image_base64: string;
  name: string;
  format: string;
}

export type SystemHealthResponse = HealthSnapshot;
export type SystemStatsResponse = StatsSnapshot;
export type ObservabilityErrorsData = ObservabilityErrorsResponse;
export type CommLogInfoResponse = CommLogInfo;
export type ConnectionTestData = ConnectionTestResponse;
