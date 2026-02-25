/**
 * UI Theme & Style Tokens
 */

import type { ThemeColors, ThemeTransitions, ThemeUiDimensions } from './theme.types';

export type { ThemeColors, ThemeTransitions, ThemeUiDimensions } from './theme.types';

export const COLORS: ThemeColors = {
  // Chart Series (Should match CSS Variables)
  series: {
    speed: 'var(--color-speed)',
    press: 'var(--color-press)',
    spot: 'var(--color-spot)',
    temp_f: 'var(--color-temp_f)',
    temp_b: 'var(--color-temp_b)',
    billet_len: 'var(--color-billet-len)',
    count: 'var(--color-count)',
    endpos: 'var(--color-endpos)',
    billet_temp: 'var(--color-billet-temp)',
    env_temp: 'var(--color-env-temp)',
    env_pre: 'var(--color-env-pre)',
  },
  
  // State Colors
  state: {
    ok: 'var(--state-ok)',
    warn: 'var(--state-warn)',
    danger: 'var(--state-danger)',
    offline: 'var(--state-offline)',
    cool: 'var(--state-cool)',
    idle: 'var(--state-idle)',
  },

  // Semantic
  primary: 'var(--text-primary)',
  secondary: 'var(--text-secondary)',
  muted: 'var(--text-muted)',
  accent: 'var(--accent-main)',
  background: 'var(--bg-main)',
  card: 'var(--bg-card)',
  border: 'var(--border-main)',
};

export const UI_DIMENSIONS: ThemeUiDimensions = {
  header_height: 'var(--header-height)',
  card_radius: 'var(--card-radius)',
  card_padding: 'var(--card-padding)',
  card_gap: 'var(--card-gap)',
};

export const TRANSITIONS: ThemeTransitions = {
  default: '0.2s ease',
  long: '0.5s ease',
};
