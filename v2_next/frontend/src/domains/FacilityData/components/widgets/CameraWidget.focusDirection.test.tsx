import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import type { SpotConfig } from '../../../../shared/types';
import type { SpotImageResponseMetadata } from '../../api/spotService.types';
import { CameraComponent } from './CameraWidget';

const buildSpotConfig = (): SpotConfig => ({
  image_url: '/api/spot/image.jpg',
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
    source: 'upstream',
    captured_at: capturedAt,
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
      spotControlError: null,
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

  it('does not couple the JPEG display to a separate temperature badge', () => {
    useDashboardStore.setState({
      spotConfig: buildSpotConfig(),
      spotImageUrl: '/api/spot/image.jpg',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: Date.now(),
      spotImageMetadata: buildSpotImageMetadata(),
    });

    render(<CameraComponent focusBusy={false} />);

    expect(document.querySelector('.camera-internal-temperature-badge')).toBeNull();
  });

  it('renders the shared validated blob and delegates display completion to the view model', () => {
    const handleImageLoad = vi.fn();
    const handleImageError = vi.fn();
    useDashboardStore.setState({
      spotConfig: buildSpotConfig(),
      spotImageUrl: 'blob:spot-image',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: Date.now(),
      spotImageMetadata: buildSpotImageMetadata(),
    });

    const { container } = render(
      <CameraComponent
        focusBusy={false}
        onSpotImageLoaded={handleImageLoad}
        onSpotImageError={handleImageError}
      />
    );
    const image = container.querySelector('img.camera-image');

    expect(image).toHaveAttribute('src', 'blob:spot-image');
    expect(container.querySelector('img[aria-hidden="true"]')).toBeNull();

    fireEvent.load(image as HTMLImageElement);
    fireEvent.error(image as HTMLImageElement);

    expect(handleImageLoad).toHaveBeenCalledTimes(1);
    expect(handleImageError).toHaveBeenCalledTimes(1);
  });

  it('exposes an explicit retry action when the shared image state has an error', () => {
    const retryImage = vi.fn();
    useDashboardStore.setState({
      spotConfig: buildSpotConfig(),
      spotImageUrl: 'blob:last-valid-spot-image',
      spotImageLoading: false,
      spotImageError: 'SPOT image upstream request failed.',
      spotLastSuccessAt: Date.now(),
      spotImageMetadata: buildSpotImageMetadata(),
    });

    render(<CameraComponent focusBusy={false} onSpotImageRetry={retryImage} />);

    fireEvent.click(screen.getByRole('button', { name: /retry spot camera image/i }));

    expect(retryImage).toHaveBeenCalledTimes(1);
  });

  it('renders control errors separately without exposing image retry', () => {
    useDashboardStore.setState({
      spotConfig: buildSpotConfig(),
      spotImageUrl: 'blob:last-valid-spot-image',
      spotImageLoading: false,
      spotImageError: null,
      spotControlError: 'SPOT actuator control failed',
      spotLastSuccessAt: Date.now(),
      spotImageMetadata: buildSpotImageMetadata(),
    });

    render(<CameraComponent focusBusy={false} onSpotImageRetry={vi.fn()} />);

    expect(screen.getByRole('alert')).toHaveTextContent('SPOT actuator control failed');
    expect(screen.queryByRole('button', { name: /retry spot camera image/i })).toBeNull();
  });

  it('uses finite crosshair geometry when the SPOT config response is missing SVG fields', () => {
    useDashboardStore.setState({
      spotConfig: {
        image_url: '',
        refresh_interval: 3,
      } as SpotConfig,
    });

    const { container } = render(<CameraComponent focusBusy={false} />);
    const svg = container.querySelector('svg.camera-crosshair');
    const lines = Array.from(container.querySelectorAll('svg.camera-crosshair line'));
    const circles = Array.from(container.querySelectorAll('svg.camera-crosshair circle'));

    expect(svg).toHaveAttribute('viewBox', '0 0 512 288');
    expect(lines).toHaveLength(8);
    expect(circles).toHaveLength(2);

    const numericAttributes = [
      ...lines.flatMap((line) => ['x1', 'y1', 'x2', 'y2'].map((attr) => line.getAttribute(attr))),
      ...circles.flatMap((circle) => ['cx', 'cy'].map((attr) => circle.getAttribute(attr))),
    ];

    numericAttributes.forEach((value) => {
      expect(value).not.toBeNull();
      expect(value).not.toBe('NaN');
      expect(value).not.toContain('undefined');
      expect(Number.isFinite(Number(value))).toBe(true);
    });
  });

});
