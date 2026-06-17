import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useShallow } from 'zustand/react/shallow';
import AlertTriangle from 'lucide-react/dist/esm/icons/alert-triangle';
import CheckCircle2 from 'lucide-react/dist/esm/icons/check-circle-2';
import RefreshCw from 'lucide-react/dist/esm/icons/refresh-cw';
import RotateCcw from 'lucide-react/dist/esm/icons/rotate-ccw';
import Save from 'lucide-react/dist/esm/icons/save';
import { selectDashboardOperatorMetadataSlice, useDashboardStore } from '../../../../store/useDashboardStore';
import type { OperatorMetadata } from '../../../../shared/types';
import { operatorMetadataService } from '../../api/operatorMetadataService';

const PRODUCT_NO_PATTERN = /^\d{1,40}$/;
const OPERATOR_MOLD_NO_PATTERN = /^\d{1,32}$/;

const EMPTY_METADATA: OperatorMetadata = {
  product_no: '',
  operator_mold_no: '',
  valid: false,
  missing_fields: ['product_no', 'operator_mold_no'],
  updated_at: null,
  source: 'operator_input',
};

type FieldErrors = {
  productNo?: string;
  operatorMoldNo?: string;
};

const normalize = (value: string): string => value.trim();

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

  const fieldErrors = useMemo(() => validateFields(productNo, operatorMoldNo), [operatorMoldNo, productNo]);
  const hasFieldErrors = Boolean(fieldErrors.productNo || fieldErrors.operatorMoldNo);
  const dirty =
    normalize(productNo) !== serverMetadata.product_no ||
    normalize(operatorMoldNo) !== serverMetadata.operator_mold_no;
  const busy = saving || resetting;
  const hasAnyMetadataValue = Boolean(
    normalize(productNo) ||
    normalize(operatorMoldNo) ||
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

  const loadMetadata = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const metadata = await operatorMetadataService.get();
      setServerMetadata(metadata);
      setProductNo(metadata.product_no);
      setOperatorMoldNo(metadata.operator_mold_no);
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
    if (errors.productNo || errors.operatorMoldNo) {
      productInputRef.current?.focus();
      return;
    }
    setSaving(true);
    try {
      const metadata = await operatorMetadataService.update({
        product_no: normalize(productNo),
        operator_mold_no: normalize(operatorMoldNo),
      });
      setServerMetadata(metadata);
      setProductNo(metadata.product_no);
      setOperatorMoldNo(metadata.operator_mold_no);
    } catch {
      setSaveError('서버 검증 또는 저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  }, [operatorMoldNo, productNo]);

  const handleReset = useCallback(async () => {
    setTouched(true);
    setSaveError(null);
    setResetting(true);
    try {
      const metadata = await operatorMetadataService.reset();
      setServerMetadata(metadata);
      setProductNo(metadata.product_no);
      setOperatorMoldNo(metadata.operator_mold_no);
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

  const shouldShowErrors = touched || !appliedValid;

  if (loading) {
    return <div className="card operator-card"><div className="widget-loading">Loading...</div></div>;
  }

  return (
    <div className={`card operator-card ${cardStateClass}`} data-testid="operator-metadata-card">
      <div className="operator-card-status">
        <div className="operator-card-status-main">
          {appliedValid && !dirty && !saveError && !loadError ? (
            <CheckCircle2 aria-hidden="true" size={18} />
          ) : (
            <AlertTriangle aria-hidden="true" size={18} />
          )}
          <span>{statusText}</span>
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
          className="operator-save-button"
          onClick={() => void handleSave()}
          disabled={busy || hasFieldErrors || !dirty}
        >
          <Save aria-hidden="true" size={18} />
          <span>적용</span>
        </button>
      </div>
    </div>
  );
});
