/**
 * UI & Business Logic Constants
 */

// Temperature Thresholds (Match with Backend constants.py)
export const SPOT_WARN_TEMP = 580;
export const SPOT_HIGH_MIN = 540;
export const SPOT_NORMAL_MIN = 480;
export const SPOT_MAX_TEMP = 650;

// Data Series Configuration
export const SERIES_WINDOW_MINUTES = 30;
export const SERIES_SAMPLES_PER_SEC = 5;
export const SERIES_WINDOW_MS = SERIES_WINDOW_MINUTES * 60 * 1000;
export const SERIES_MAX_POINTS = SERIES_WINDOW_MINUTES * 60 * SERIES_SAMPLES_PER_SEC;

// UI Layout
export const CURRENT_LAYOUT_COLS = 60;
export const SPARKLINE_POINTS = 10;

// Auto-scaling (viewport-responsive row height)
export const DEFAULT_ROW_HEIGHT = 20;
export const MIN_ROW_HEIGHT = 12;
export const MAX_ROW_HEIGHT = 32;
export const BASE_VIEWPORT_HEIGHT = 1080;

// Business Thresholds
export const SPEED_MAX = 15;
export const PRESS_MAX = 250;
export const PRESS_RUNNING_THRESHOLD = 20;

// Alarm & Status Timers (in MS)
export const ALERT_HOLD_MS = 2000;
export const ALERT_HOLD_LONG_MS = 5000;
export const STATUS_WARN_MS = 10000;
export const STATUS_OFFLINE_MS = 20000;
export const SETTINGS_AUTO_REFRESH_MS = 4000;
export const OBSERVABILITY_REFRESH_MS = 10000;

// Monitoring Metrics
export const STATUS_ERROR_RATE_WARN = 0.2;
export const STATUS_P95_WARN_MS = 800;
export const STATUS_RECENT_ERROR_MS = 60000;

// Storage Keys
export const LAYOUT_STORAGE_KEY = 'grafana_scene_layout_v1';
export const LAYOUT_BACKUP_KEY = 'grafana_scene_layout_v1_backup';
export const FRONT_ERROR_STORAGE_KEY = 'sfl_front_errors';
export const FRONT_ERROR_MAX = 50;
export const OBSERVABILITY_ERROR_LIMIT = 50;
export const EXPORT_PATH_STORAGE_KEY = 'sfl_observability_export_path';

// Client-local layout storage
export const LOCAL_LAYOUT_STORAGE_KEY = 'sfl_local_layout';
export const STORAGE_MODE_KEY = 'sfl_storage_mode';
export type { StorageMode } from './logic.types';

