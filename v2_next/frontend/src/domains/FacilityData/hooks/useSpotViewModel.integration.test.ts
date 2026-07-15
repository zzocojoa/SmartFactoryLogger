import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi, type MockedFunction } from 'vitest';
import { useSpotViewModel } from './useSpotViewModel';
import { useDashboardStore } from '../../../store/useDashboardStore';
import type { SpotConfig } from '../../../shared/types';
import type { SpotFocusResponse } from '../../../shared/api/transport/spotService.transport';

const mocks = vi.hoisted(() => ({
  fetchSpotConfig: vi.fn<() => Promise<SpotConfig>>(),
  fetchSpotImageResponse: vi.fn<() => Promise<Response>>(),
  controlSpotFocus: vi.fn<(steps: number) => Promise<SpotFocusResponse>>(),
  controlSpotActuator: vi.fn<(step: number) => Promise<void>>(),
}));

const mockFetchSpotConfig = mocks.fetchSpotConfig;
const mockFetchSpotImageResponse = mocks.fetchSpotImageResponse;
const mockControlSpotFocus: MockedFunction<(steps: number) => Promise<SpotFocusResponse>> = mocks.controlSpotFocus;
const mockControlSpotActuator = mocks.controlSpotActuator;

vi.mock('./useSpotViewModel.service', () => ({
  fetchSpotConfig: () => mockFetchSpotConfig(),
  fetchSpotImageResponse: () => mockFetchSpotImageResponse(),
  controlSpotAction: () => Promise.resolve(undefined),
  controlSpotFocus: (steps: number) => mockControlSpotFocus(steps),
  controlSpotActuator: (step: number) => mockControlSpotActuator(step),
}));

vi.mock('../../../shared/api/client', () => ({
  API_BASE: '/api',
}));

vi.mock('./useSpotViewModelEffects', () => ({
  useSpotViewModelEffects: () => undefined,
}));

const BASE_SPOT_CONFIG: SpotConfig = {
  image_url: '/api/spot/image.jpg',
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

const buildTransientResponse = (code = 'upstream-timeout', upstreamStatus?: number): Response =>
  new Response(
    JSON.stringify({
      detail: {
        code,
        upstream_status: upstreamStatus,
      },
    }),
    {
      status: 502,
      headers: {
        ...Object.fromEntries(buildHeaders(true).entries()),
        'Content-Type': 'application/json',
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
    mockControlSpotActuator.mockResolvedValue(undefined);
    useDashboardStore.setState({
      spotImageUrl: '',
      spotImageLoading: false,
      spotImageError: null,
      spotControlError: null,
      spotLastSuccessAt: null,
      spotImageMetadata: null,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    mockFetchSpotConfig.mockReset();
    mockFetchSpotImageResponse.mockReset();
    mockControlSpotFocus.mockReset();
    mockControlSpotActuator.mockReset();
  });

  it('publishes payload rejection to shared state and recovers through explicit retry', async () => {
    const originalCreateObjectURL = global.URL.createObjectURL;
    const originalRevokeObjectURL = global.URL.revokeObjectURL;
    global.URL.createObjectURL = vi.fn(() => 'blob:mocked-spot-image');
    global.URL.revokeObjectURL = vi.fn();
    const consoleErrorMock = vi.spyOn(console, 'error').mockImplementation((): void => undefined);

    const setSpotImageStateMock = vi.fn();
    const originalSetSpotImageState = useDashboardStore.getState().setSpotImageState;
    useDashboardStore.setState({
      ...useDashboardStore.getState(),
      setSpotImageState: setSpotImageStateMock,
    });

    mockFetchSpotConfig.mockResolvedValue(BASE_SPOT_CONFIG);
    mockFetchSpotImageResponse.mockResolvedValueOnce(buildValidJpegResponse());
    mockFetchSpotImageResponse.mockResolvedValueOnce(buildRejectionResponse());
    mockFetchSpotImageResponse.mockResolvedValueOnce(buildValidJpegResponse());

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

      expect(setSpotImageStateMock).toHaveBeenCalledTimes(3);
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
          source: 'camera',
        }),
      );
      const [nextImageUrl, nextImageLoading, nextImageError] = setSpotImageStateMock.mock.calls[1];
      expect(nextImageUrl).toContain('blob:');
      expect(nextImageLoading).toBe(false);
      expect(nextImageError).toBeNull();
      expect(setSpotImageStateMock).toHaveBeenNthCalledWith(
        3,
        nextImageUrl,
        false,
        expect.stringContaining('payload rejected'),
        expect.any(Number),
        expect.objectContaining({
          source: 'camera',
        })
      );
      const errorStateCalls = setSpotImageStateMock.mock.calls.filter(([, ,imageError]) => imageError !== null);
      expect(errorStateCalls).toHaveLength(1);
      expect(result.current.imageError).toBeTruthy();
      expect(result.current.diagnostics.error_count).toBe(1);
      expect(consoleErrorMock).toHaveBeenCalledWith(
        'Spot image payload validation failed',
        expect.objectContaining({
          event: 'spot_image_payload_rejected',
          code: 'invalid-image-format',
          responseStatus: 502,
        })
      );

      await act(async () => {
        await result.current.refreshImage();
      });

      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(3);
      expect(setSpotImageStateMock).toHaveBeenCalledTimes(4);
      expect(setSpotImageStateMock).toHaveBeenLastCalledWith(
        expect.stringContaining('blob:'),
        false,
        null,
        expect.any(Number),
        expect.objectContaining({
          source: 'camera',
        })
      );
      expect(result.current.imageError).toBeNull();
    } finally {
      unmount();
      mockFetchSpotConfig.mockReset();
      mockFetchSpotImageResponse.mockReset();
      consoleErrorMock.mockRestore();
      global.URL.createObjectURL = originalCreateObjectURL;
      global.URL.revokeObjectURL = originalRevokeObjectURL;
      useDashboardStore.setState({
        ...useDashboardStore.getState(),
        setSpotImageState: originalSetSpotImageState,
      });
    }
  });

  it('clears shared loading state when the first image payload is rejected', async () => {
    const consoleErrorMock = vi.spyOn(console, 'error').mockImplementation((): void => undefined);
    useDashboardStore.setState({
      spotImageUrl: '',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: null,
      spotImageMetadata: null,
    });
    mockFetchSpotConfig.mockResolvedValue(BASE_SPOT_CONFIG);
    mockFetchSpotImageResponse.mockResolvedValueOnce(buildRejectionResponse());

    const { result, unmount } = renderHook(() => useSpotViewModel());

    try {
      await act(async () => {
        await result.current.refreshConfig();
      });
      await act(async () => {
        await result.current.refreshImage();
      });

      const sharedImageState = useDashboardStore.getState();
      expect(sharedImageState.spotImageUrl).toBe('');
      expect(sharedImageState.spotImageLoading).toBe(false);
      expect(sharedImageState.spotImageError).toContain('payload rejected');
      expect(sharedImageState.spotLastSuccessAt).toBeNull();
      expect(result.current.imageLoading).toBe(false);
      expect(result.current.diagnostics.error_count).toBe(1);
    } finally {
      unmount();
      mockFetchSpotConfig.mockReset();
      mockFetchSpotImageResponse.mockReset();
      consoleErrorMock.mockRestore();
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

  it('requests the next image after display completion and auto-recovers after display error', async () => {
    const originalCreateObjectURL = global.URL.createObjectURL;
    const originalRevokeObjectURL = global.URL.revokeObjectURL;
    global.URL.createObjectURL = vi.fn(() => `blob:spot-${mockFetchSpotImageResponse.mock.calls.length}`);
    global.URL.revokeObjectURL = vi.fn();
    mockFetchSpotConfig.mockResolvedValue(BASE_SPOT_CONFIG);
    mockFetchSpotImageResponse.mockImplementation(async () => buildValidJpegResponse());

    const { result, unmount } = renderHook(() => useSpotViewModel());

    try {
      await act(async () => {
        await result.current.refreshConfig();
      });
      act(() => {
        result.current.refreshImage();
      });
      await waitFor(() => expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(1));

      act(() => {
        result.current.handleImageLoad('blob:stale-consumer-frame');
      });
      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(1);

      act(() => {
        result.current.handleImageLoad(result.current.imageUrl);
      });
      await waitFor(() => expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(2));

      vi.useFakeTimers();
      act(() => {
        result.current.handleImageError();
      });
      expect(result.current.diagnostics.automatic_retry_pending).toBe(true);
      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(2);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(500);
      });
      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(3);
    } finally {
      unmount();
      mockFetchSpotConfig.mockReset();
      mockFetchSpotImageResponse.mockReset();
      global.URL.createObjectURL = originalCreateObjectURL;
      global.URL.revokeObjectURL = originalRevokeObjectURL;
    }
  });

  it('automatically retries a transient timeout and clears the image error on success', async () => {
    vi.useFakeTimers();
    const originalCreateObjectURL = global.URL.createObjectURL;
    const originalRevokeObjectURL = global.URL.revokeObjectURL;
    global.URL.createObjectURL = vi.fn(() => 'blob:auto-recovered');
    global.URL.revokeObjectURL = vi.fn();
    const consoleErrorMock = vi.spyOn(console, 'error').mockImplementation((): void => undefined);
    mockFetchSpotConfig.mockResolvedValue(BASE_SPOT_CONFIG);
    mockFetchSpotImageResponse
      .mockResolvedValueOnce(buildTransientResponse())
      .mockImplementation(async () => buildValidJpegResponse());

    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => {
        await result.current.refreshConfig();
      });
      await act(async () => {
        result.current.refreshImage();
        await Promise.resolve();
      });
      await act(async () => {
        await Promise.resolve();
      });

      expect(result.current.imageError).toBeTruthy();
      expect(result.current.diagnostics.automatic_retry_count).toBe(1);
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(1);
      expect(result.current.diagnostics.automatic_retry_pending).toBe(true);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(499);
      });
      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(1);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(2);
      expect(result.current.imageError).toBeNull();

      await act(async () => {
        result.current.handleImageLoad(result.current.imageUrl);
        await Promise.resolve();
      });
      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(3);
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(0);
      expect(result.current.diagnostics.automatic_retry_exhausted).toBe(false);
    } finally {
      unmount();
      consoleErrorMock.mockRestore();
      global.URL.createObjectURL = originalCreateObjectURL;
      global.URL.revokeObjectURL = originalRevokeObjectURL;
    }
  });

  it('does not automatically retry a persistent payload rejection', async () => {
    vi.useFakeTimers();
    const consoleErrorMock = vi.spyOn(console, 'error').mockImplementation((): void => undefined);
    mockFetchSpotConfig.mockResolvedValue(BASE_SPOT_CONFIG);
    mockFetchSpotImageResponse.mockResolvedValue(buildRejectionResponse());

    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => {
        await result.current.refreshConfig();
      });
      await act(async () => {
        result.current.refreshImage();
        await Promise.resolve();
      });
      await act(async () => {
        await Promise.resolve();
        await vi.advanceTimersByTimeAsync(10_000);
      });

      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(1);
      expect(result.current.diagnostics.last_failure_retryable).toBe(false);
      expect(result.current.diagnostics.automatic_retry_pending).toBe(false);
    } finally {
      unmount();
      consoleErrorMock.mockRestore();
    }
  });

  it('stops after three automatic retries and leaves manual recovery available', async () => {
    vi.useFakeTimers();
    const originalCreateObjectURL = global.URL.createObjectURL;
    const originalRevokeObjectURL = global.URL.revokeObjectURL;
    global.URL.createObjectURL = vi.fn(() => 'blob:recovered-after-exhaustion');
    global.URL.revokeObjectURL = vi.fn();
    const consoleErrorMock = vi.spyOn(console, 'error').mockImplementation((): void => undefined);
    mockFetchSpotConfig.mockResolvedValue(BASE_SPOT_CONFIG);
    mockFetchSpotImageResponse.mockResolvedValue(buildTransientResponse());

    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => {
        await result.current.refreshConfig();
      });
      await act(async () => {
        result.current.refreshImage();
        await Promise.resolve();
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(500);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1_000);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_000);
      });

      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(4);
      expect(result.current.diagnostics.automatic_retry_count).toBe(3);
      expect(result.current.diagnostics.automatic_retry_exhausted).toBe(true);
      expect(result.current.diagnostics.automatic_retry_pending).toBe(false);
      expect(result.current.imageError).toBeTruthy();

      mockFetchSpotImageResponse.mockResolvedValueOnce(buildValidJpegResponse());
      await act(async () => {
        result.current.refreshImage();
        await Promise.resolve();
      });
      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(5);
      expect(result.current.imageError).toBeNull();
      expect(result.current.diagnostics.automatic_retry_exhausted).toBe(false);
    } finally {
      unmount();
      consoleErrorMock.mockRestore();
      global.URL.createObjectURL = originalCreateObjectURL;
      global.URL.revokeObjectURL = originalRevokeObjectURL;
    }
  });

  it('manual retry cancels the pending timer and requests immediately', async () => {
    vi.useFakeTimers();
    const originalCreateObjectURL = global.URL.createObjectURL;
    const originalRevokeObjectURL = global.URL.revokeObjectURL;
    global.URL.createObjectURL = vi.fn(() => 'blob:manual-recovered');
    global.URL.revokeObjectURL = vi.fn();
    const consoleErrorMock = vi.spyOn(console, 'error').mockImplementation((): void => undefined);
    mockFetchSpotConfig.mockResolvedValue(BASE_SPOT_CONFIG);
    mockFetchSpotImageResponse
      .mockResolvedValueOnce(buildTransientResponse())
      .mockResolvedValueOnce(buildValidJpegResponse());

    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => {
        await result.current.refreshConfig();
      });
      await act(async () => {
        result.current.refreshImage();
        await Promise.resolve();
      });
      await act(async () => {
        await Promise.resolve();
      });
      expect(result.current.diagnostics.automatic_retry_pending).toBe(true);

      await act(async () => {
        result.current.refreshImage();
        await Promise.resolve();
      });
      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(2);
      expect(result.current.diagnostics.automatic_retry_pending).toBe(false);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_000);
      });
      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(2);
    } finally {
      unmount();
      consoleErrorMock.mockRestore();
      global.URL.createObjectURL = originalCreateObjectURL;
      global.URL.revokeObjectURL = originalRevokeObjectURL;
    }
  });

  it('keeps focus and actuator failures out of the image error state', async () => {
    const consoleErrorMock = vi.spyOn(console, 'error').mockImplementation((): void => undefined);
    mockControlSpotFocus.mockRejectedValueOnce(new Error('focus unavailable'));
    mockControlSpotActuator.mockRejectedValueOnce(new Error('actuator unavailable'));
    const { result, unmount } = renderHook(() => useSpotViewModel());

    try {
      await act(async () => {
        await result.current.controlFocus(1);
      });
      expect(result.current.imageError).toBeNull();
      expect(useDashboardStore.getState().spotImageError).toBeNull();
      expect(useDashboardStore.getState().spotControlError).toBe('focus unavailable');

      await act(async () => {
        await result.current.controlActuator(1);
      });
      expect(result.current.imageError).toBeNull();
      expect(useDashboardStore.getState().spotControlError).toBe('actuator unavailable');

      await act(async () => {
        await result.current.controlActuator(1);
      });
      expect(useDashboardStore.getState().spotControlError).toBeNull();
    } finally {
      unmount();
      consoleErrorMock.mockRestore();
    }
  });

  it('deduplicates automatic retry scheduling across duplicate display errors', async () => {
    vi.useFakeTimers();
    const originalCreateObjectURL = global.URL.createObjectURL;
    const originalRevokeObjectURL = global.URL.revokeObjectURL;
    global.URL.createObjectURL = vi.fn(() => 'blob:duplicate-display-error');
    global.URL.revokeObjectURL = vi.fn();
    mockFetchSpotConfig.mockResolvedValue(BASE_SPOT_CONFIG);
    mockFetchSpotImageResponse.mockImplementation(async () => buildValidJpegResponse());

    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => {
        await result.current.refreshConfig();
      });
      await act(async () => {
        result.current.refreshImage();
        await Promise.resolve();
      });
      const failedUrl = result.current.imageUrl;

      act(() => {
        result.current.handleImageError(failedUrl);
        result.current.handleImageError(failedUrl);
      });
      expect(result.current.diagnostics.automatic_retry_count).toBe(1);
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(1);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(500);
      });
      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(2);
    } finally {
      unmount();
      global.URL.createObjectURL = originalCreateObjectURL;
      global.URL.revokeObjectURL = originalRevokeObjectURL;
    }
  });

  it('cancels a pending automatic retry when the hook unmounts', async () => {
    vi.useFakeTimers();
    const consoleErrorMock = vi.spyOn(console, 'error').mockImplementation((): void => undefined);
    mockFetchSpotConfig.mockResolvedValue(BASE_SPOT_CONFIG);
    mockFetchSpotImageResponse.mockResolvedValue(buildTransientResponse());

    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => {
        await result.current.refreshConfig();
      });
      await act(async () => {
        result.current.refreshImage();
        await Promise.resolve();
      });
      expect(result.current.diagnostics.automatic_retry_pending).toBe(true);

      unmount();
      await vi.advanceTimersByTimeAsync(1_000);
      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(1);
    } finally {
      consoleErrorMock.mockRestore();
    }
  });

  it('cancels a pending automatic retry when the image route changes', async () => {
    vi.useFakeTimers();
    const consoleErrorMock = vi.spyOn(console, 'error').mockImplementation((): void => undefined);
    mockFetchSpotConfig
      .mockResolvedValueOnce(BASE_SPOT_CONFIG)
      .mockResolvedValueOnce({ ...BASE_SPOT_CONFIG, image_url: '/api/spot/image-v2.jpg' });
    mockFetchSpotImageResponse.mockResolvedValue(buildTransientResponse());

    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => {
        await result.current.refreshConfig();
      });
      await act(async () => {
        result.current.refreshImage();
        await Promise.resolve();
      });
      expect(result.current.diagnostics.automatic_retry_pending).toBe(true);

      await act(async () => {
        await result.current.refreshConfig();
      });
      await vi.advanceTimersByTimeAsync(1_000);
      expect(mockFetchSpotImageResponse).toHaveBeenCalledTimes(1);
      expect(result.current.diagnostics.automatic_retry_pending).toBe(false);
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(0);
    } finally {
      unmount();
      consoleErrorMock.mockRestore();
    }
  });
});
