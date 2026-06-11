import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import type { SpotConfig } from '../../../../shared/types';
import type { SpotImageResponseMetadata } from '../../api/spotService.types';
import { CameraComponent, resolveSpotLiveImageUrl } from './CameraWidget';

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
    vi.useRealTimers();
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

  it('renders live image endpoint and reloads it after onLoad without replacing proxy lifecycle image', () => {
    vi.useFakeTimers();
    useDashboardStore.setState({
      spotConfig: {
        ...buildSpotConfig(),
        live_image_url: '/api/spot/live_image',
      },
      spotImageUrl: 'blob:spot-proxy-snapshot',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: Date.now(),
      spotImageMetadata: buildSpotImageMetadata(),
    });

    const { container } = render(<CameraComponent focusBusy={false} />);
    const liveImage = container.querySelector('img.camera-image');
    const lifecycleImage = container.querySelector('img[aria-hidden="true"]');

    expect(liveImage).toBeInstanceOf(HTMLImageElement);
    expect(liveImage?.getAttribute('src')).toMatch(/^\/api\/spot\/live_image\?t=/);
    expect(lifecycleImage?.getAttribute('src')).toBe('blob:spot-proxy-snapshot');

    const firstSrc = liveImage?.getAttribute('src');
    fireEvent.load(liveImage as HTMLImageElement);

    act(() => {
      vi.advanceTimersByTime(34);
    });
    expect(liveImage?.getAttribute('src')).toBe(firstSrc);

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(liveImage?.getAttribute('src')).toMatch(/^\/api\/spot\/live_image\?t=/);
    expect(liveImage?.getAttribute('src')).not.toBe(firstSrc);
  });

  it('resolves relative live image URLs against the API base for Electron file views', () => {
    expect(resolveSpotLiveImageUrl('/api/spot/live_image', 'http://localhost:8000')).toBe(
      'http://localhost:8000/api/spot/live_image'
    );
    expect(resolveSpotLiveImageUrl('api/spot/live_image', 'http://localhost:8000/')).toBe(
      'http://localhost:8000/api/spot/live_image'
    );
    expect(resolveSpotLiveImageUrl('http://127.0.0.1:8000/api/spot/live_image', 'http://localhost:8000')).toBe(
      'http://127.0.0.1:8000/api/spot/live_image'
    );
  });
});
