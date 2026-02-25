export interface ThemeSeriesColors {
  speed: string;
  press: string;
  spot: string;
  temp_f: string;
  temp_b: string;
  billet_len: string;
  count: string;
  endpos: string;
  billet_temp: string;
  env_temp: string;
  env_pre: string;
}

export interface ThemeStateColors {
  ok: string;
  warn: string;
  danger: string;
  offline: string;
  cool: string;
  idle: string;
}

export interface ThemeColors {
  series: ThemeSeriesColors;
  state: ThemeStateColors;
  primary: string;
  secondary: string;
  muted: string;
  accent: string;
  background: string;
  card: string;
  border: string;
}

export interface ThemeUiDimensions {
  header_height: string;
  card_radius: string;
  card_padding: string;
  card_gap: string;
}

export interface ThemeTransitions {
  default: string;
  long: string;
}
