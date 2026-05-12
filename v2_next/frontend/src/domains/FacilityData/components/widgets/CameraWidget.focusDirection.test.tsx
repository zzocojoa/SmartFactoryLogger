import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import type { SpotConfig } from '../../../../shared/types';
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
});
