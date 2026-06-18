import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useShallow } from 'zustand/react/shallow';
import AlertTriangle from 'lucide-react/dist/esm/icons/alert-triangle';
import CheckCircle2 from 'lucide-react/dist/esm/icons/check-circle-2';
import Flag from 'lucide-react/dist/esm/icons/flag';
import RefreshCw from 'lucide-react/dist/esm/icons/refresh-cw';
import RotateCcw from 'lucide-react/dist/esm/icons/rotate-ccw';
import Save from 'lucide-react/dist/esm/icons/save';
import { selectDashboardOperatorMetadataSlice, useDashboardStore } from '../../../../store/useDashboardStore';
import type { OperatorMetadata } from '../../../../shared/types';
import { operatorMetadataService } from '../../api/operatorMetadataService';

const PRODUCT_NO_PATTERN = /^\d{1,40}$/;
const OPERATOR_MOLD_NO_PATTERN = /^\d{1,32}$/;
const REQUIRED_ALERT_RING_COUNT = 9;
const REQUIRED_ALERT_RING_INDICES = Array.from({ length: REQUIRED_ALERT_RING_COUNT }, (_, index) => index);

const EMPTY_METADATA: OperatorMetadata = {
  product_no: '',
  operator_mold_no: '',
  valid: false,
  missing_fields: ['product_no', 'operator_mold_no'],
  updated_at: null,
  source: 'operator_input',
  history: [],
};

type FieldErrors = {
  productNo?: string;
  operatorMoldNo?: string;
};

type OperatorMetadataViewState = 'missing' | 'invalid' | 'dirty' | 'applied' | 'stale';

const normalize = (value: string | null | undefined): string => (value ?? '').trim();

const normalizeOperatorMetadata = (metadata: Partial<OperatorMetadata> | null | undefined): OperatorMetadata => {
  const productNo = typeof metadata?.product_no === 'string' ? metadata.product_no : '';
  const operatorMoldNo = typeof metadata?.operator_mold_no === 'string' ? metadata.operator_mold_no : '';
  const rawMissingFields = metadata?.missing_fields;
  const missingFields = Array.isArray(rawMissingFields)
    ? rawMissingFields.filter((field): field is string => typeof field === 'string')
    : [
        ...(!productNo ? ['product_no'] : []),
        ...(!operatorMoldNo ? ['operator_mold_no'] : []),
      ];
  const rawHistory = metadata?.history;
  const history = Array.isArray(rawHistory)
    ? rawHistory
        .filter((entry): entry is OperatorMetadata['history'][number] => (
          typeof entry?.product_no === 'string' &&
          typeof entry?.operator_mold_no === 'string'
        ))
        .map((entry) => ({
          product_no: entry.product_no,
          operator_mold_no: entry.operator_mold_no,
          updated_at: typeof entry.updated_at === 'string' ? entry.updated_at : null,
        }))
        .slice(0, 3)
    : [];

  return {
    product_no: productNo,
    operator_mold_no: operatorMoldNo,
    valid: typeof metadata?.valid === 'boolean' ? metadata.valid : missingFields.length === 0,
    missing_fields: missingFields,
    updated_at: typeof metadata?.updated_at === 'string' ? metadata.updated_at : null,
    source: typeof metadata?.source === 'string' ? metadata.source : 'operator_input',
    history,
  };
};

const validateProductNo = (value: string): string | undefined => {
  if (!normalize(value)) {
    return '제품번호는 필수입니다.';
  }
  if (!PRODUCT_NO_PATTERN.test(value)) {
    return '숫자만 입력할 수 있습니다.';
  }
  return undefined;
};

const validateOperatorMoldNo = (value: string): string | undefined => {
  if (!normalize(value)) {
    return '금형 번호는 필수입니다.';
  }
  if (!OPERATOR_MOLD_NO_PATTERN.test(value)) {
    return '숫자만 입력할 수 있습니다.';
  }
  return undefined;
};

const validateFields = (productNo: string, operatorMoldNo: string): FieldErrors => {
  const errors: FieldErrors = {};
  const productNoError = validateProductNo(productNo);
  const moldNoError = validateOperatorMoldNo(operatorMoldNo);
  if (productNoError) {
    errors.productNo = productNoError;
  }
  if (moldNoError) {
    errors.operatorMoldNo = moldNoError;
  }
  return errors;
};

const formatAppliedAt = (value?: string | null): string => {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
};

export const OperatorMetadataComponent = React.memo(function OperatorMetadataComponent() {
  const applied = useDashboardStore(useShallow(selectDashboardOperatorMetadataSlice));
  const productInputRef = useRef<HTMLInputElement | null>(null);
  const [serverMetadata, setServerMetadata] = useState<OperatorMetadata>(EMPTY_METADATA);
  const [productNo, setProductNo] = useState('');
  const [operatorMoldNo, setOperatorMoldNo] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);
  const [changeNeeded, setChangeNeeded] = useState(false);
  const [requiredAlertActive, setRequiredAlertActive] = useState(false);
  const [requiredAlertNonce, setRequiredAlertNonce] = useState(0);

  const fieldErrors = useMemo(() => validateFields(productNo, operatorMoldNo), [operatorMoldNo, productNo]);
  const hasFieldErrors = Boolean(fieldErrors.productNo || fieldErrors.operatorMoldNo);
  const normalizedProductNo = normalize(productNo);
  const normalizedOperatorMoldNo = normalize(operatorMoldNo);
  const dirty =
    normalizedProductNo !== serverMetadata.product_no ||
    normalizedOperatorMoldNo !== serverMetadata.operator_mold_no;
  const busy = saving || resetting;
  const hasAnyMetadataValue = Boolean(
    normalizedProductNo ||
    normalizedOperatorMoldNo ||
    serverMetadata.product_no ||
    serverMetadata.operator_mold_no
  );
  const appliedValid = serverMetadata.valid;
  const cardStateClass = loadError || saveError || !appliedValid ? 'card-danger' : dirty ? 'card-warning' : '';
  const statusText = loadError
    ? '불러오기 실패'
    : saveError
      ? '저장 실패'
      : resetting
        ? '리셋 중'
        : saving
          ? '저장 중'
        : !appliedValid
          ? '필수값 미입력'
          : dirty
            ? '미저장 변경'
            : '적용됨';

  const inputMissing = !normalizedProductNo || !normalizedOperatorMoldNo;
  const hasFormatErrors = Boolean(
    (normalizedProductNo && fieldErrors.productNo) ||
    (normalizedOperatorMoldNo && fieldErrors.operatorMoldNo)
  );
  const viewState = useMemo<OperatorMetadataViewState>(() => {
    if (hasFormatErrors) {
      return 'invalid';
    }
    if (inputMissing) {
      return 'missing';
    }
    if (dirty) {
      return 'dirty';
    }
    if (!appliedValid) {
      return 'missing';
    }
    if (changeNeeded) {
      return 'stale';
    }
    return 'applied';
  }, [appliedValid, changeNeeded, dirty, hasFormatErrors, inputMissing]);
  const effectiveCardStateClass =
    loadError || saveError || viewState === 'missing' || viewState === 'invalid'
      ? 'card-danger operator-card-required'
      : viewState === 'dirty'
        ? `${cardStateClass === 'card-warning' ? cardStateClass : 'card-warning'} operator-card-attention`
        : viewState === 'stale'
          ? 'card-warning operator-card-attention'
          : 'operator-card-applied';
  const effectiveStatusText = loadError || saveError || saving || resetting
    ? statusText
    : viewState === 'missing'
      ? '필수값 미입력'
      : viewState === 'invalid'
        ? '입력값 확인 필요'
        : viewState === 'dirty'
          ? '미저장 변경'
          : viewState === 'stale'
            ? '제품 변경 확인 필요'
            : '적용됨';
  const canSave = !busy && !hasFieldErrors && (dirty || changeNeeded);
  const saveBlocked = !canSave;
  const changeBlocked = busy || !appliedValid;
  const appliedMetadataMissing =
    !serverMetadata.valid ||
    serverMetadata.missing_fields.length > 0 ||
    !serverMetadata.product_no ||
    !serverMetadata.operator_mold_no;
  const showRequiredAlert = !loading && requiredAlertActive && (inputMissing || appliedMetadataMissing);
  const previousJobs = serverMetadata.history.slice(0, 3);

  const triggerRequiredAlert = useCallback(() => {
    setTouched(true);
    setRequiredAlertActive(true);
    setRequiredAlertNonce((current) => current + 1);
    productInputRef.current?.focus();
  }, []);

  const loadMetadata = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const metadata = normalizeOperatorMetadata(await operatorMetadataService.get());
      setServerMetadata(metadata);
      setProductNo(metadata.product_no);
      setOperatorMoldNo(metadata.operator_mold_no);
      setTouched(false);
      setChangeNeeded(false);
      setRequiredAlertActive(false);
    } catch {
      setLoadError('작업자 입력값을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMetadata();
  }, [loadMetadata]);

  useEffect(() => {
    if (!loading && !serverMetadata.valid && productInputRef.current) {
      productInputRef.current.focus();
    }
  }, [loading, serverMetadata.valid]);

  const handleSave = useCallback(async () => {
    setTouched(true);
    setSaveError(null);
    const errors = validateFields(productNo, operatorMoldNo);
    const missingRequiredValue = !normalize(productNo) || !normalize(operatorMoldNo);
    if (missingRequiredValue) {
      triggerRequiredAlert();
      return;
    }
    if (errors.productNo || errors.operatorMoldNo) {
      productInputRef.current?.focus();
      return;
    }
    if (!dirty && !changeNeeded) {
      return;
    }
    setSaving(true);
    try {
      const metadata = normalizeOperatorMetadata(await operatorMetadataService.update({
        product_no: normalize(productNo),
        operator_mold_no: normalize(operatorMoldNo),
      }));
      setServerMetadata(metadata);
      setProductNo(metadata.product_no);
      setOperatorMoldNo(metadata.operator_mold_no);
      setTouched(false);
      setChangeNeeded(false);
      setRequiredAlertActive(false);
    } catch {
      setSaveError('서버 검증 또는 저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  }, [changeNeeded, dirty, operatorMoldNo, productNo, triggerRequiredAlert]);

  const handleReset = useCallback(async () => {
    setTouched(true);
    setSaveError(null);
    setResetting(true);
    try {
      const metadata = normalizeOperatorMetadata(await operatorMetadataService.reset());
      setServerMetadata(metadata);
      setProductNo(metadata.product_no);
      setOperatorMoldNo(metadata.operator_mold_no);
      setChangeNeeded(false);
      setRequiredAlertActive(false);
      productInputRef.current?.focus();
    } catch {
      setSaveError('서버 저장값 리셋에 실패했습니다.');
    } finally {
      setResetting(false);
    }
  }, []);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>): void => {
    if (event.key === 'Enter') {
      event.preventDefault();
      void handleSave();
    }
  };

  const handleMarkChangeNeeded = useCallback(() => {
    setTouched(true);
    if (inputMissing) {
      triggerRequiredAlert();
      return;
    }
    if (hasFieldErrors) {
      productInputRef.current?.focus();
      return;
    }
    if (!appliedValid) {
      productInputRef.current?.focus();
      return;
    }
    setChangeNeeded(true);
    productInputRef.current?.focus();
  }, [appliedValid, hasFieldErrors, inputMissing, triggerRequiredAlert]);

  const shouldShowErrors = touched || viewState === 'missing' || viewState === 'invalid';

  if (loading) {
    return <div className="card operator-card"><div className="widget-loading">Loading...</div></div>;
  }

  return (
    <div
      className={`card operator-card ${effectiveCardStateClass} ${showRequiredAlert ? 'operator-card-alert-active' : ''}`}
      data-testid="operator-metadata-card"
      data-state={loadError ? 'load-error' : saveError ? 'save-error' : viewState}
    >
      {showRequiredAlert && (
        <div
          key={requiredAlertNonce}
          className="operator-card-alert-glow"
          data-testid="operator-metadata-required-alert"
          data-alert-nonce={requiredAlertNonce}
          aria-hidden="true"
        >
          <span className="operator-card-alert-base-glow" />
          <span className="operator-card-alert-rays">
            <span className="operator-card-alert-rays-line" />
            <span className="operator-card-alert-rays-line operator-card-alert-rays-line-soft" />
          </span>
          <span className="operator-card-alert-rings">
            {REQUIRED_ALERT_RING_INDICES.map((index) => (
              <span key={index} className="operator-card-alert-ring" />
            ))}
          </span>
          <span className="operator-card-alert-core operator-card-alert-core-blur" />
          <span className="operator-card-alert-core" />
        </div>
      )}

      <div className="operator-card-status">
        <div className="operator-card-status-main">
          {viewState === 'applied' && !saveError && !loadError ? (
            <CheckCircle2 aria-hidden="true" size={18} />
          ) : (
            <AlertTriangle aria-hidden="true" size={18} />
          )}
          <span className="operator-state-badge">{effectiveStatusText}</span>
        </div>
        <span className="operator-card-updated">최근 적용 {formatAppliedAt(serverMetadata.updated_at ?? applied.updatedAt)}</span>
      </div>

      <div className="operator-form-grid">
        <label className="operator-field">
          <span className="operator-field-label">제품번호</span>
          <input
            ref={productInputRef}
            value={productNo}
            maxLength={40}
            inputMode="numeric"
            pattern="[0-9]*"
            placeholder="12345"
            aria-label="제품번호"
            aria-invalid={Boolean(shouldShowErrors && fieldErrors.productNo)}
            onChange={(event) => setProductNo(event.target.value)}
            onBlur={() => setTouched(true)}
            onKeyDown={handleKeyDown}
          />
          {shouldShowErrors && fieldErrors.productNo && (
            <span className="operator-field-error" role="alert">{fieldErrors.productNo}</span>
          )}
        </label>

        <label className="operator-field">
          <span className="operator-field-label">금형 번호</span>
          <input
            value={operatorMoldNo}
            maxLength={32}
            inputMode="numeric"
            pattern="[0-9]*"
            placeholder="123"
            aria-label="금형 번호"
            aria-invalid={Boolean(shouldShowErrors && fieldErrors.operatorMoldNo)}
            onChange={(event) => setOperatorMoldNo(event.target.value)}
            onBlur={() => setTouched(true)}
            onKeyDown={handleKeyDown}
          />
          {shouldShowErrors && fieldErrors.operatorMoldNo && (
            <span className="operator-field-error" role="alert">{fieldErrors.operatorMoldNo}</span>
          )}
        </label>
      </div>

      {(loadError || saveError) && (
        <div className="operator-card-message" role="alert">
          {loadError || saveError}
        </div>
      )}

      <div className="operator-history" data-testid="operator-metadata-history">
        <div className="operator-history-title">이전 작업</div>
        {previousJobs.length > 0 ? (
          <div className="operator-history-list">
            {previousJobs.map((entry, index) => (
              <div
                className="operator-history-row"
                key={`${entry.updated_at ?? 'unknown'}:${entry.product_no}:${entry.operator_mold_no}:${index}`}
              >
                <span className="operator-history-time">{formatAppliedAt(entry.updated_at)}</span>
                <span className="operator-history-values">{entry.product_no}, {entry.operator_mold_no}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="operator-history-empty">기록 없음</div>
        )}
      </div>

      <div className="operator-card-actions">
        <button
          type="button"
          className="operator-icon-button"
          onClick={() => void loadMetadata()}
          disabled={busy}
          title="서버 값 새로고침"
          aria-label="서버 값 새로고침"
        >
          <RefreshCw aria-hidden="true" size={18} />
        </button>
        <button
          type="button"
          className="operator-icon-button"
          onClick={() => void handleReset()}
          disabled={busy || !hasAnyMetadataValue}
          title="서버 저장값 리셋"
          aria-label="서버 저장값 리셋"
        >
          <RotateCcw aria-hidden="true" size={18} />
        </button>
        <button
          type="button"
          className={`operator-change-button ${changeNeeded ? 'active' : ''}`}
          onClick={handleMarkChangeNeeded}
          disabled={busy}
          data-disabled={changeBlocked}
          title="제품 변경 표시"
          aria-label="Mark product change needed"
          data-testid="operator-metadata-change-needed"
        >
          <Flag aria-hidden="true" size={18} />
          <span>제품 변경</span>
        </button>
        <button
          type="button"
          className={`operator-save-button ${viewState === 'dirty' || viewState === 'stale' ? 'operator-save-emphasis' : ''}`}
          onClick={() => void handleSave()}
          disabled={busy}
          data-disabled={saveBlocked}
          data-testid="operator-metadata-apply"
        >
          <Save aria-hidden="true" size={18} />
          <span>적용</span>
        </button>
      </div>
    </div>
  );
});
