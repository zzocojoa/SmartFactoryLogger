import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi, type MockedFunction } from 'vitest';
import { useSpotViewModel } from './useSpotViewModel';
import { useDashboardStore } from '../../../store/useDashboardStore';
import type { SpotConfig } from '../../../shared/types';
import type { SpotFocusResponse } from '../../../shared/api/transport/spotService.transport';

const mocks = vi.hoisted(() => ({
  fetchSpotConfig: vi.fn<() => Promise<SpotConfig>>(),
  fetchSpotImageResponse: vi.fn<() => Promise<Response>>(),
  controlSpotFocus: vi.fn<(steps: number) => Promise<SpotFocusResponse>>(),
}));

const mockFetchSpotConfig = mocks.fetchSpotConfig;
const mockFetchSpotImageResponse = mocks.fetchSpotImageResponse;
const mockControlSpotFocus: MockedFunction<(steps: number) => Promise<SpotFocusResponse>> = mocks.controlSpotFocus;

vi.mock('./useSpotViewModel.service', () => ({
  fetchSpotConfig: () => mockFetchSpotConfig(),
  fetchSpotImageResponse: () => mockFetchSpotImageResponse(),
  controlSpotAction: () => Promise.resolve(undefined),
  controlSpotFocus: (steps: number) => mockControlSpotFocus(steps),
  controlSpotActuator: () => Promise.resolve(undefined),
}));

vi.mock('../../../shared/api/client', () => ({
  API_BASE: '/api',
}));

vi.mock('./useSpotViewModelEffects', () => ({
  useSpotViewModelEffects: () => undefined,
}));

const BASE_SPOT_CONFIG: SpotConfig = {
  image_url: '/api/spot/proxy_image',
  refresh_interval: 3,
  crosshair_x: 0.5,
  crosshair_y: 0.5,
  crosshair_color: '#ffffff',
  crosshair_thickness: 2,
  crosshair_size: 80,
  crosshair_gap: 6,
  widget_width: 320,
  widget_height: 240,
  focus_step: 10,
  actuator_step: 5,
  focus_enabled: true,
};

const buildHeaders = (isError: boolean): Headers => {
  const headers = new Headers({
    'X-Spot-Image-Status': isError ? 'error' : 'ok',
    'X-Spot-Cache-Status': 'fresh',
    'X-Spot-Proxy-State': isError ? 'error' : 'ok',
    'X-Spot-Image-Source': 'camera',
    'X-Spot-Image-Age': '0.250',
  });
  return headers;
};

const buildValidJpegResponse = (): Response => {
  const bytes = new Uint8Array(20);
  bytes[0] = 0xff;
  bytes[1] = 0xd8;
  bytes[18] = 0xff;
  bytes[19] = 0xd9;

  return new Response(bytes, {
    status: 200,
    headers: {
      ...Object.fromEntries(buildHeaders(false).entries()),
      'Content-Type': 'image/jpeg',
      'Content-Length': String(bytes.byteLength),
    },
  });
};

const buildRejectionResponse = (): Response =>
  new Response(
    JSON.stringify({
      detail: {
        code: 'invalid-image-html',
        message: 'payload rejected',
      },
    }),
    {
      status: 502,
      headers: {
        ...Object.fromEntries(buildHeaders(true).entries()),
        'Content-Type': 'application/json',
        'X-Spot-Payload-Rejection': '1',
      },
    }
  );

describe('useSpotViewModel integration', () => {
  beforeEach(() => {
    mockControlSpotFocus.mockResolvedValue({
      status: 'ok',
      current: 100,
      new: 95,
      verified: 95,
      request_steps: -1,
      focus_step: 5,
    });
  });

  afterEach(() => {
    mockControlSpotFocus.mockReset();
  });

  it('does not call setSpotImageState when spot image fetch payload is rejected', async () => {
    const originalCreateObjectURL = global.URL.createObjectURL;
    const originalRevokeObjectURL = global.URL.revokeObjectURL;
    global.URL.createObjectURL = vi.fn(() => 'blob:mocked-spot-image');
    global.URL.revokeObjectURL = vi.fn();

    const setSpotImageStateMock = vi.fn();
    const originalSetSpotImageState = useDashboardStore.getState().setSpotImageState;
    useDashboardStore.setState({
      ...useDashboardStore.getState(),
      setSpotImageState: setSpotImageStateMock,
    });

    mockFetchSpotConfig.mockResolvedValue(BASE_SPOT_CONFIG);
    mockFetchSpotImageResponse.mockResolvedValueOnce(buildValidJpegResponse());
    mockFetchSpotImageResponse.mockResolvedValueOnce(buildRejectionResponse());

    const { result, unmount } = renderHook(() => useSpotViewModel());

    try {
      await act(async () => {
        await result.current.refreshConfig();
      });

      await act(async () => {
        await result.current.refreshImage();
      });

      await act(async () => {
        await result.current.refreshImage();
      });

      expect(setSpotImageStateMock).toHaveBeenCalledTimes(2);
      expect(setSpotImageStateMock).toHaveBeenNthCalledWith(
        1,
        '',
        true,
        null,
        null,
        null
      );
      expect(setSpotImageStateMock).toHaveBeenNthCalledWith(
        2,
        expect.stringContaining('blob:'),
        false,
        null,
        expect.any(Number),
        expect.objectContaining({
          status: 'ok',
          raw_status: 'ok',
          cache_status: 'fresh',
        }),
      );
      const [nextImageUrl, nextImageLoading, nextImageError] =
        setSpotImageStateMock.mock.calls[1];
      expect(nextImageUrl).toContain('blob:');
      expect(nextImageLoading).toBe(false);
      expect(nextImageError).toBeNull();
      const errorStateCalls = setSpotImageStateMock.mock.calls.filter(([, ,imageError]) => imageError !== null);
      expect(errorStateCalls).toHaveLength(0);
      expect(result.current.imageError).toBeTruthy();
    } finally {
      unmount();
      mockFetchSpotConfig.mockReset();
      mockFetchSpotImageResponse.mockReset();
      global.URL.createObjectURL = originalCreateObjectURL;
      global.URL.revokeObjectURL = originalRevokeObjectURL;
      useDashboardStore.setState({
        ...useDashboardStore.getState(),
        setSpotImageState: originalSetSpotImageState,
      });
    }
  });

  it('sends focus controls as signed unit steps without multiplying by actuator_step', async () => {
    const { result } = renderHook(() => useSpotViewModel());

    await act(async () => {
      await result.current.controlFocus(-1);
    });

    expect(mockControlSpotFocus).toHaveBeenCalledTimes(1);
    expect(mockControlSpotFocus).toHaveBeenCalledWith(-1);
  });
});
