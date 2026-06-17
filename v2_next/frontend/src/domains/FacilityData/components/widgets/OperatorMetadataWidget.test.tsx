import React from 'react';
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FactoryData, OperatorMetadata } from '../../../../shared/types';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import { OperatorMetadataComponent } from './OperatorMetadataWidget';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  update: vi.fn(),
  reset: vi.fn(),
}));

vi.mock('../../api/operatorMetadataService', () => ({
  operatorMetadataService: {
    get: mocks.get,
    update: mocks.update,
    reset: mocks.reset,
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

const buildFactoryData = (overrides: Partial<FactoryData> = {}): FactoryData => ({
  Time: '2026-03-09T07:20:20.000',
  Status: 'Running',
  Speed: 1,
  Press: 2,
  Count: 3,
  EndPos: 4,
  Billet_Length: 5,
  Spot: 6,
  Temp_F: 7,
  Temp_B: 8,
  Billet_Temp: 9,
  Mold1: 10,
  Mold2: 11,
  Mold3: 12,
  Mold4: 13,
  Mold5: 14,
  Mold6: 15,
  At_Temp: 16,
  At_Pre: 17,
  ...overrides,
});

describe('OperatorMetadataComponent', () => {
  beforeEach(() => {
    mocks.get.mockResolvedValue(buildMetadata());
    mocks.update.mockResolvedValue(buildMetadata({
      product_no: '12345',
      operator_mold_no: '123',
      valid: true,
      missing_fields: [],
      updated_at: '2026-03-09T07:20:20Z',
    }));
    mocks.reset.mockResolvedValue(buildMetadata({
      updated_at: '2026-03-09T07:21:00Z',
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

    const productInput = await screen.findByLabelText('제품번호');
    const moldInput = screen.getByLabelText('금형 번호');
    fireEvent.change(productInput, { target: { value: '12345' } });
    fireEvent.change(moldInput, { target: { value: '123' } });

    const saveButton = screen.getByRole('button', { name: /적용/i });
    expect(saveButton).toBeEnabled();
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledWith({
        product_no: '12345',
        operator_mold_no: '123',
      });
    });
  });

  it('keeps non-numeric product numbers client-side before save', async () => {
    render(<OperatorMetadataComponent />);

    const productInput = await screen.findByLabelText('제품번호');
    const moldInput = screen.getByLabelText('금형 번호');
    fireEvent.change(productInput, { target: { value: 'DW-12345' } });
    fireEvent.change(moldInput, { target: { value: '123' } });

    expect(screen.getByText('숫자만 입력할 수 있습니다.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /적용/i })).toBeDisabled();
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('keeps non-numeric mold numbers client-side before save', async () => {
    render(<OperatorMetadataComponent />);

    const productInput = await screen.findByLabelText('제품번호');
    const moldInput = screen.getByLabelText('금형 번호');
    fireEvent.change(productInput, { target: { value: '12345' } });
    fireEvent.change(moldInput, { target: { value: '123-1' } });

    expect(screen.getByText('숫자만 입력할 수 있습니다.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /적용/i })).toBeDisabled();
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('reloads server values without resetting stored metadata', async () => {
    mocks.get
      .mockResolvedValueOnce(buildMetadata({
        product_no: '11111',
        operator_mold_no: '111',
        valid: true,
        missing_fields: [],
        updated_at: '2026-03-09T07:20:20Z',
      }))
      .mockResolvedValueOnce(buildMetadata({
        product_no: '22222',
        operator_mold_no: '222',
        valid: true,
        missing_fields: [],
        updated_at: '2026-03-09T07:21:20Z',
      }));
    render(<OperatorMetadataComponent />);

    const productInput = await screen.findByLabelText('제품번호');
    const moldInput = screen.getByLabelText('금형 번호');
    expect(productInput).toHaveValue('11111');
    expect(moldInput).toHaveValue('111');

    fireEvent.click(screen.getByRole('button', { name: '서버 값 새로고침' }));

    await waitFor(() => {
      expect(screen.getByLabelText('제품번호')).toHaveValue('22222');
      expect(screen.getByLabelText('금형 번호')).toHaveValue('222');
    });
    expect(mocks.get).toHaveBeenCalledTimes(2);
    expect(mocks.reset).not.toHaveBeenCalled();
  });

  it('resets persisted operator metadata and returns to required missing state', async () => {
    mocks.get.mockResolvedValueOnce(buildMetadata({
      product_no: '12345',
      operator_mold_no: '123',
      valid: true,
      missing_fields: [],
      updated_at: '2026-03-09T07:20:20Z',
    }));
    useDashboardStore.getState().setData(buildFactoryData({
      Product_No_operator: '12345',
      Mold_No_operator: '123',
      operator_metadata_valid: true,
      operator_metadata_missing_fields: [],
      operator_metadata_updated_at: '2026-03-09T07:20:20Z',
    }), Date.now());
    render(<OperatorMetadataComponent />);

    const productInput = await screen.findByLabelText('제품번호');
    const moldInput = screen.getByLabelText('금형 번호');
    fireEvent.click(screen.getByRole('button', { name: '서버 저장값 리셋' }));

    await waitFor(() => {
      expect(mocks.reset).toHaveBeenCalledTimes(1);
    });
    expect(productInput).toHaveValue('');
    expect(moldInput).toHaveValue('');
    expect(screen.getByText('필수값 미입력')).toBeInTheDocument();
    expect(screen.getByText('제품번호는 필수입니다.')).toBeInTheDocument();
    expect(screen.getByText('금형 번호는 필수입니다.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /적용/i })).toBeDisabled();
  });
});
