import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import type { SpotConfig } from '../../../../shared/types';
import type { SpotImageResponseMetadata } from '../../api/spotService.types';
import { CameraComponent } from './CameraWidget';

const buildSpotConfig = (): SpotConfig => ({
  image_url: '/api/spot/proxy_image',
  refresh_interval: 3,
  crosshair_x: 0.5,
  crosshair_y: 0.5,
  crosshair_color: 'lime',
  crosshair_thickness: 2,
  crosshair_size: 20,
  crosshair_gap: 5,
  widget_width: 512,
  widget_height: 288,
  focus_step: 50,
  actuator_step: 50,
  focus_enabled: true,
});

const buildSpotImageMetadata = (): SpotImageResponseMetadata => {
  const capturedAt: number = Date.now();
  return {
    status: 'ok',
    raw_status: 'ok',
    cache_status: 'fresh',
    raw_cache_status: 'fresh',
    proxy_state: 'ok',
    raw_proxy_state: 'ok',
    source: 'cache',
    age_sec: 0.25,
    max_stale_age_sec: 15,
    captured_at: capturedAt,
    internal_temperature: 41.25,
    internal_temperature_at: capturedAt,
    internal_temperature_status: 'ok',
    retry_after_sec: null,
    received_at: capturedAt + 250,
    latency_ms: 12,
  };
};

describe('CameraComponent focus direction controls', () => {
  afterEach(() => {
    cleanup();
    useDashboardStore.setState({
      spotConfig: null,
      spotImageUrl: '',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: null,
      spotImageMetadata: null,
    });
  });

  it('sends the physical left direction as a positive actuator step', () => {
    const requestFocus = vi.fn<(steps: number) => void>();
    useDashboardStore.setState({ spotConfig: buildSpotConfig() });

    render(<CameraComponent requestFocus={requestFocus} focusBusy={false} />);

    fireEvent.click(screen.getByRole('button', { name: /left/i }));

    expect(requestFocus).toHaveBeenCalledTimes(1);
    expect(requestFocus).toHaveBeenCalledWith(1);
  });

  it('sends the physical right direction as a negative actuator step', () => {
    const requestFocus = vi.fn<(steps: number) => void>();
    useDashboardStore.setState({ spotConfig: buildSpotConfig() });

    render(<CameraComponent requestFocus={requestFocus} focusBusy={false} />);

    fireEvent.click(screen.getByRole('button', { name: /right/i }));

    expect(requestFocus).toHaveBeenCalledTimes(1);
    expect(requestFocus).toHaveBeenCalledWith(-1);
  });

  it('renders the internal temperature badge text from spot image metadata', () => {
    useDashboardStore.setState({
      spotConfig: buildSpotConfig(),
      spotImageUrl: '/api/spot/proxy_image',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: Date.now(),
      spotImageMetadata: buildSpotImageMetadata(),
    });

    render(<CameraComponent focusBusy={false} />);

    const badge = screen.getByText(/41\.3°C/);
    expect(badge).toHaveClass('camera-internal-temperature-badge');
  });
});
