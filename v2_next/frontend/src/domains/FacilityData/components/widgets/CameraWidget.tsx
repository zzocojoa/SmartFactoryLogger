/**
 * Camera Widget - SPOT 카메라 이미지 + 크로스헤어 표시
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React from 'react';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import { API_BASE } from '../../../../shared/api/client';
import { getCameraStatus } from '../../../../shared/utils/commBadge';
import { LABELS, SPOT_UNIT } from '../../../../shared/constants/uiText';

const SPOT_LIVE_IMAGE_RELOAD_DELAY_MS = 35;
const SPOT_LIVE_IMAGE_ERROR_RETRY_DELAY_MS = 500;

interface CameraComponentProps {
  onSpotImageLoaded?: () => void;
  onSpotImageError?: () => void;
  requestFocus?: (steps: number) => void;
  focusBusy?: boolean;
}

const formatSpotInternalTemperatureBadge = (temperature: number | null, status: string | null): string | null => {
  if (status !== null && status.trim().toLowerCase() !== 'ok') {
    return null;
  }
  if (temperature === null || !Number.isFinite(temperature)) {
    return null;
  }
  return `내부 ${temperature.toFixed(1)}${SPOT_UNIT}`;
};

const appendSpotLiveCacheBuster = (url: string, token: number): string => {
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}t=${encodeURIComponent(String(token))}`;
};

export const resolveSpotLiveImageUrl = (url: string, apiBase: string): string => {
  const trimmedUrl = url.trim();
  if (!trimmedUrl) {
    return '';
  }
  if (/^[a-z][a-z\d+\-.]*:\/\//i.test(trimmedUrl) || trimmedUrl.startsWith('//')) {
    return trimmedUrl;
  }
  if (!apiBase) {
    return trimmedUrl;
  }
  const normalizedApiBase = apiBase.replace(/\/+$/, '');
  if (trimmedUrl.startsWith('/')) {
    return `${normalizedApiBase}${trimmedUrl}`;
  }
  return `${normalizedApiBase}/${trimmedUrl}`;
};

export const CameraComponent = React.memo(function CameraComponent(props: CameraComponentProps) {
  const spotConfig = useDashboardStore(state => state.spotConfig);
  const spotImageUrl = useDashboardStore(state => state.spotImageUrl);
  const spotImageLoading = useDashboardStore(state => state.spotImageLoading);
  const spotImageError = useDashboardStore(state => state.spotImageError);
  const spotLastSuccessAt = useDashboardStore(state => state.spotLastSuccessAt);
  const spotImageMetadata = useDashboardStore(state => state.spotImageMetadata);
  const liveImageRef = React.useRef<HTMLImageElement | null>(null);
  const liveImageTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const liveImageFrameRef = React.useRef(0);
  const liveImageUrl = resolveSpotLiveImageUrl(spotConfig?.live_image_url ?? '', API_BASE);
  const hasLiveImageUrl = liveImageUrl.length > 0;
  const initialLiveImageSrc = React.useMemo(
    () => hasLiveImageUrl ? appendSpotLiveCacheBuster(liveImageUrl, Date.now()) : '',
    [hasLiveImageUrl, liveImageUrl]
  );

  const clearLiveImageTimer = React.useCallback((): void => {
    if (liveImageTimerRef.current !== null) {
      clearTimeout(liveImageTimerRef.current);
      liveImageTimerRef.current = null;
    }
  }, []);

  const scheduleLiveImageReload = React.useCallback(
    (delayMs: number): void => {
      if (!hasLiveImageUrl) {
        return;
      }
      clearLiveImageTimer();
      liveImageTimerRef.current = setTimeout(() => {
        const image = liveImageRef.current;
        if (!image) {
          return;
        }
        liveImageFrameRef.current += 1;
        image.src = appendSpotLiveCacheBuster(liveImageUrl, Date.now() + liveImageFrameRef.current);
      }, delayMs);
    },
    [clearLiveImageTimer, hasLiveImageUrl, liveImageUrl]
  );

  React.useEffect(() => {
    clearLiveImageTimer();
    liveImageFrameRef.current += 1;
    const image = liveImageRef.current;
    if (image && hasLiveImageUrl) {
      image.src = appendSpotLiveCacheBuster(liveImageUrl, Date.now() + liveImageFrameRef.current);
    }
    return clearLiveImageTimer;
  }, [clearLiveImageTimer, hasLiveImageUrl, liveImageUrl]);

  const handleLiveImageLoad = React.useCallback((): void => {
    scheduleLiveImageReload(SPOT_LIVE_IMAGE_RELOAD_DELAY_MS);
  }, [scheduleLiveImageReload]);

  const handleLiveImageError = React.useCallback((): void => {
    scheduleLiveImageReload(SPOT_LIVE_IMAGE_ERROR_RETRY_DELAY_MS);
  }, [scheduleLiveImageReload]);

  if (!spotConfig) return <div>Loading Config...</div>;

  // Crosshair logic
  const clamp = (val: number, min: number, max: number) => Math.min(max, Math.max(min, val));
  const cx = clamp(spotConfig.crosshair_x, 0, 1) * spotConfig.widget_width;
  const cy = clamp(spotConfig.crosshair_y, 0, 1) * spotConfig.widget_height;
  const arm = Math.max(1, spotConfig.crosshair_size);
  const gap = Math.max(0, spotConfig.crosshair_gap);
  const thick = Math.max(1, spotConfig.crosshair_thickness);
  const color = spotConfig.crosshair_color || 'lime';

  const lines = [
    { x1: cx - gap, y1: cy, x2: cx - arm, y2: cy },
    { x1: cx + gap, y1: cy, x2: cx + arm, y2: cy },
    { x1: cx, y1: cy - gap, x2: cx, y2: cy - arm },
    { x1: cx, y1: cy + gap, x2: cx, y2: cy + arm },
  ];

  const cameraStatus = getCameraStatus({
    spotConfig,
    spotImageUrl,
    spotImageLoading,
    spotImageError,
    spotLastSuccessAt,
    spotImageMetadata,
  });
  const internalTemperatureBadgeText: string | null = cameraStatus
    ? null
    : formatSpotInternalTemperatureBadge(
        spotImageMetadata?.internal_temperature ?? null,
        spotImageMetadata?.internal_temperature_status ?? null
      );
  const actuatorStep = Math.abs(spotConfig.actuator_step);
  const actuatorStepValid = Number.isFinite(actuatorStep) && actuatorStep > 0;
  const focusDisabled = !spotConfig.focus_enabled || !props.requestFocus || Boolean(props.focusBusy) || !actuatorStepValid;
  const focusDisabledReason = !spotConfig.focus_enabled
    ? 'Focus control is disabled'
    : !props.requestFocus
      ? 'Focus control handler is missing'
      : !actuatorStepValid
        ? `Invalid actuator step: ${spotConfig.actuator_step}`
        : undefined;
  const requestFocusChange = (stepUnits: number): void => {
    if (!props.requestFocus) {
      throw new Error('SPOT focus request handler is missing');
    }
    props.requestFocus(stepUnits);
  };

  return (
    <div className="card camera-card" style={{ height: '100%', position: 'relative' }}>
      <div className="camera-frame">
        {hasLiveImageUrl ? (
          <img
            ref={liveImageRef}
            className="camera-image"
            src={initialLiveImageSrc}
            alt={LABELS.SPOT_CAMERA}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            onLoad={handleLiveImageLoad}
            onError={handleLiveImageError}
            decoding="async"
          />
        ) : spotImageUrl ? (
          <img
            className="camera-image"
            src={spotImageUrl}
            alt={LABELS.SPOT_CAMERA}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            onLoad={props.onSpotImageLoaded}
            onError={props.onSpotImageError}
            loading="lazy"
            decoding="async"
          />
        ) : null}
        {hasLiveImageUrl && spotImageUrl && (
          <img
            src={spotImageUrl}
            alt=""
            aria-hidden="true"
            style={{ position: 'absolute', width: 1, height: 1, opacity: 0, pointerEvents: 'none' }}
            onLoad={props.onSpotImageLoaded}
            onError={props.onSpotImageError}
          />
        )}
        <svg className="camera-crosshair" viewBox={`0 0 ${spotConfig.widget_width} ${spotConfig.widget_height}`} preserveAspectRatio="xMidYMid slice" style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
          {lines.map((line, idx) => (
            <g key={idx}>
              <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} stroke="black" strokeWidth={thick + 2} strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
              <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} stroke={color} strokeWidth={thick} strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
            </g>
          ))}
          <circle cx={cx} cy={cy} r={3} stroke="black" strokeWidth={3} fill="none" vectorEffect="non-scaling-stroke" />
          <circle cx={cx} cy={cy} r={3} stroke={color} strokeWidth={1} fill="none" vectorEffect="non-scaling-stroke" />
        </svg>
        {internalTemperatureBadgeText && (
          <div className="camera-internal-temperature-badge">
            {internalTemperatureBadgeText}
          </div>
        )}
        {cameraStatus && (
          <div className={`camera-overlay ${cameraStatus.type}`} style={{ pointerEvents: 'none' }}>
            {cameraStatus.type === 'loading' && <span className="camera-spinner" aria-hidden="true" />}
            <div className="camera-status-text">
              <div className="camera-status-title">{cameraStatus.title}</div>
              {cameraStatus.detail && <div className="camera-status-detail">{cameraStatus.detail}</div>}
            </div>
          </div>
        )}
      </div>
      <div className="camera-controls" style={{ marginTop: '4px' }}>
        <button
          type="button"
          disabled={focusDisabled}
          title={focusDisabledReason}
          aria-label={`Move SPOT actuator left ${actuatorStep}`}
          onClick={() => requestFocusChange(1)}
        >
          &lt;-Focus
        </button>
        <button
          type="button"
          disabled={focusDisabled}
          title={focusDisabledReason}
          aria-label={`Move SPOT actuator right ${actuatorStep}`}
          onClick={() => requestFocusChange(-1)}
        >
          Focus -&gt;
        </button>
      </div>
    </div>
  );
}
);
