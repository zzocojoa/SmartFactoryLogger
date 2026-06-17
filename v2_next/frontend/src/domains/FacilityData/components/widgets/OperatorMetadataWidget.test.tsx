import React from 'react';
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { OperatorMetadata } from '../../../../shared/types';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import { OperatorMetadataComponent } from './OperatorMetadataWidget';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  update: vi.fn(),
}));

vi.mock('../../api/operatorMetadataService', () => ({
  operatorMetadataService: {
    get: mocks.get,
    update: mocks.update,
  },
}));

const buildMetadata = (overrides: Partial<OperatorMetadata> = {}): OperatorMetadata => ({
  product_no: '',
  operator_mold_no: '',
  valid: false,
  missing_fields: ['product_no', 'operator_mold_no'],
  updated_at: null,
  source: 'operator_input',
  ...overrides,
});

describe('OperatorMetadataComponent', () => {
  beforeEach(() => {
    mocks.get.mockResolvedValue(buildMetadata());
    mocks.update.mockResolvedValue(buildMetadata({
      product_no: 'DW-50306',
      operator_mold_no: 'MOLD-01',
      valid: true,
      missing_fields: [],
      updated_at: '2026-03-09T07:20:20Z',
    }));
    useDashboardStore.getState().setData(null, null);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    useDashboardStore.getState().setData(null, null);
  });

  it('shows required missing state and disables apply until both fields are valid', async () => {
    render(<OperatorMetadataComponent />);

    expect(await screen.findByText('필수값 미입력')).toBeInTheDocument();
    expect(screen.getByText('제품번호는 필수입니다.')).toBeInTheDocument();
    expect(screen.getByText('금형 번호는 필수입니다.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /적용/i })).toBeDisabled();
  });

  it('saves valid operator metadata through the backend API', async () => {
    render(<OperatorMetadataComponent />);

    const productInput = await screen.findByLabelText('제품번호(DW-)');
    const moldInput = screen.getByLabelText('금형 번호');
    fireEvent.change(productInput, { target: { value: 'DW-50306' } });
    fireEvent.change(moldInput, { target: { value: 'MOLD-01' } });

    const saveButton = screen.getByRole('button', { name: /적용/i });
    expect(saveButton).toBeEnabled();
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledWith({
        product_no: 'DW-50306',
        operator_mold_no: 'MOLD-01',
      });
    });
  });

  it('keeps invalid DW product numbers client-side before save', async () => {
    render(<OperatorMetadataComponent />);

    const productInput = await screen.findByLabelText('제품번호(DW-)');
    const moldInput = screen.getByLabelText('금형 번호');
    fireEvent.change(productInput, { target: { value: 'PX-50306' } });
    fireEvent.change(moldInput, { target: { value: 'MOLD-01' } });

    expect(screen.getByText('DW-로 시작하고 영문, 숫자, ., _, -만 사용할 수 있습니다.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /적용/i })).toBeDisabled();
    expect(mocks.update).not.toHaveBeenCalled();
  });
});
