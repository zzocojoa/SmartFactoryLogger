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

export interface ConfigSpotPayload {
  ip?: string;
  refresh_interval?: number;
  actuator_step: number;
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
  current_password?: string;
}

export interface ConfigLoggingPayload {
  rotation_enabled: boolean;
  rotation_mode: string;
  cycle_idle_time?: number;
  cycle_threshold_press?: number;
}

export interface ConfigSystemPayload {
  interval_sec: number;
  status_warn_ms?: number;
  status_offline_ms?: number;
}

export interface ConfigMesPayload {
  enabled: boolean;
  userid?: string;
  password?: string;
  starthour: number;
  endhour: number;
}

export interface ConfigPayload {
  extruder: ConfigConnectionPayload;
  ls_plc: ConfigConnectionPayload;
  spot: ConfigSpotPayload;
  thresholds: ConfigThresholdsPayload;
  settings: ConfigSettingsPayload;
  logging: ConfigLoggingPayload;
  system: ConfigSystemPayload;
  mes: ConfigMesPayload;
}

export type GenericApiResponse = Record<string, unknown>;
