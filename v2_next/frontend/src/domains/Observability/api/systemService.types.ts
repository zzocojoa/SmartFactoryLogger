import type {
  CommLogInfo,
  ConnectionTestResponse,
  HealthSnapshot,
  MemoryDetailsResponse,
  MemoryStateResponse,
  ObservabilityErrorsResponse,
  PathHealthResult,
  StatsSnapshot,
} from '../../../shared/types';

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

export interface MemoryExportRequest {
  frontend: Record<string, unknown>;
}

export type SystemHealthResponse = HealthSnapshot;
export type SystemStatsResponse = StatsSnapshot;
export type ObservabilityErrorsData = ObservabilityErrorsResponse;
export type CommLogInfoResponse = CommLogInfo;
export type ConnectionTestData = ConnectionTestResponse;
export type MemoryStateData = MemoryStateResponse;
export type MemoryDetailsData = MemoryDetailsResponse;
