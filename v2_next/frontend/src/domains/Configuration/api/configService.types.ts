export interface OverridePayload {
  enabled: boolean;
  password?: string;
  actor: string;
}

export interface PasswordVerificationResponse {
  ok: boolean;
}

export interface ConfigConnectionPayload {
  ip?: string;
  port?: number;
}

export type ConfigSpotImageCaptureMode = 'off' | 'event' | 'interval' | 'all';

export interface ConfigSpotImageCapturePayload {
  enabled: boolean;
  mode: ConfigSpotImageCaptureMode;
  path: string;
  min_interval_sec: number;
  max_bytes: number;
  retention_days: number;
  link_to_observation: boolean;
}

export interface ConfigSpotPayload {
  ip?: string;
  refresh_interval?: number;
  actuator_step: number;
  image_capture?: ConfigSpotImageCapturePayload;
}

export interface ConfigThresholdEnablePayload {
  master_on: boolean;
  speed: boolean;
  press: boolean;
  spot: boolean;
  temp_f: boolean;
  temp_b: boolean;
  billet: boolean;
  billet_temp: boolean;
  at_temp: boolean;
  at_pre: boolean;
  count: boolean;
  endpos: boolean;
}

export interface ConfigThresholdValuesPayload {
  speed: string;
  press: string;
  spot: string;
  temp_f: string;
  temp_b: string;
  billet: string;
  billet_temp: string;
  at_temp: string;
  at_pre: string;
  count: string;
  endpos: string;
}

export interface ConfigThresholdsPayload {
  enable: ConfigThresholdEnablePayload;
  values: ConfigThresholdValuesPayload;
}

export interface ConfigSettingsPayload {
  logpath?: string;
  snapshotpath?: string;
  autosave: boolean;
  password?: string;
  operator_metadata_downtime_reset_hours: number;
  current_password?: string;
}

export interface ConfigSystemPayload {
  interval_sec: number;
  status_warn_ms?: number;
  status_offline_ms?: number;
}

export interface ConfigPayload {
  extruder: ConfigConnectionPayload;
  ls_plc: ConfigConnectionPayload;
  spot: ConfigSpotPayload;
  thresholds: ConfigThresholdsPayload;
  settings: ConfigSettingsPayload;
  system: ConfigSystemPayload;
}

export type GenericApiResponse = Record<string, unknown>;
