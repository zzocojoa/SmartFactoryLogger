import React from 'react';
import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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
  history: [],
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
    vi.useRealTimers();
    vi.clearAllMocks();
    useDashboardStore.getState().setData(null, null);
  });

  it('shows required missing state and triggers the RGB alert without saving', async () => {
    render(<OperatorMetadataComponent />);

    expect(await screen.findByText('필수값 미입력')).toBeInTheDocument();
    expect(screen.getByText('제품번호는 필수입니다.')).toBeInTheDocument();
    expect(screen.getByText('금형 번호는 필수입니다.')).toBeInTheDocument();
    expect(screen.queryByTestId('operator-metadata-required-alert')).not.toBeInTheDocument();
    const applyButton = screen.getByTestId('operator-metadata-apply');
    expect(applyButton).not.toBeDisabled();
    expect(applyButton).toHaveAttribute('data-disabled', 'true');

    fireEvent.click(applyButton);

    expect(screen.getByTestId('operator-metadata-required-alert')).toHaveAttribute('data-alert-nonce', '1');
    expect(document.querySelectorAll('.operator-card-alert-ring')).toHaveLength(14);
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('starts the required RGB alert from an action when metadata load fails before Electron can apply server state', async () => {
    mocks.get.mockRejectedValueOnce(new Error('metadata unavailable'));

    render(<OperatorMetadataComponent />);

    const card = await screen.findByTestId('operator-metadata-card');
    expect(card).toHaveAttribute('data-state', 'load-error');
    expect(card).not.toHaveClass('operator-card-alert-active');
    expect(screen.queryByTestId('operator-metadata-required-alert')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('operator-metadata-apply'));

    expect(card).toHaveClass('operator-card-alert-active');
    expect(screen.getByTestId('operator-metadata-required-alert')).toHaveAttribute('data-alert-nonce', '1');
  });

  it('restarts the required RGB alert when missing apply is clicked repeatedly', async () => {
    render(<OperatorMetadataComponent />);

    const applyButton = await screen.findByTestId('operator-metadata-apply');
    expect(screen.queryByTestId('operator-metadata-required-alert')).not.toBeInTheDocument();

    fireEvent.click(applyButton);
    expect(screen.getByTestId('operator-metadata-required-alert')).toHaveAttribute('data-alert-nonce', '1');

    fireEvent.click(applyButton);
    expect(screen.getByTestId('operator-metadata-required-alert')).toHaveAttribute('data-alert-nonce', '2');
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('triggers the required RGB alert from Enter save when required values are missing', async () => {
    render(<OperatorMetadataComponent />);

    await screen.findByTestId('operator-metadata-apply');
    expect(screen.queryByTestId('operator-metadata-required-alert')).not.toBeInTheDocument();
    const [productInput] = screen.getAllByRole('textbox');

    fireEvent.keyDown(productInput, { key: 'Enter' });

    expect(screen.getByTestId('operator-metadata-required-alert')).toHaveAttribute('data-alert-nonce', '1');
    expect(document.querySelectorAll('.operator-card-alert-ring')).toHaveLength(14);
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('triggers the required RGB alert from product-change action when required values are missing', async () => {
    render(<OperatorMetadataComponent />);

    const changeButton = await screen.findByTestId('operator-metadata-change-needed');
    expect(changeButton).not.toBeDisabled();
    expect(changeButton).toHaveAttribute('data-disabled', 'true');
    expect(screen.queryByTestId('operator-metadata-required-alert')).not.toBeInTheDocument();

    fireEvent.click(changeButton);

    expect(screen.getByTestId('operator-metadata-required-alert')).toHaveAttribute('data-alert-nonce', '1');
    expect(document.querySelectorAll('.operator-card-alert-ring')).toHaveLength(14);
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('keeps the required RGB alert until valid values are applied', async () => {
    render(<OperatorMetadataComponent />);

    const applyButton = await screen.findByTestId('operator-metadata-apply');
    expect(screen.queryByTestId('operator-metadata-required-alert')).not.toBeInTheDocument();

    fireEvent.click(applyButton);
    expect(screen.getByTestId('operator-metadata-required-alert')).toBeInTheDocument();

    const [productInput, moldInput] = screen.getAllByRole('textbox');
    fireEvent.change(productInput, { target: { value: '12345' } });
    fireEvent.change(moldInput, { target: { value: '123' } });

    expect(screen.getByTestId('operator-metadata-required-alert')).toBeInTheDocument();
    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledWith({
        product_no: '12345',
        operator_mold_no: '123',
      });
      expect(screen.queryByTestId('operator-metadata-required-alert')).not.toBeInTheDocument();
    });
    expect(productInput).not.toHaveAttribute('aria-invalid', 'true');
    expect(moldInput).not.toHaveAttribute('aria-invalid', 'true');
  });

  it('keeps the required RGB alert during silent refresh while server metadata is still invalid', async () => {
    vi.useFakeTimers();
    mocks.get.mockResolvedValue(buildMetadata());
    render(<OperatorMetadataComponent />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    fireEvent.click(screen.getByTestId('operator-metadata-apply'));
    expect(screen.getByTestId('operator-metadata-required-alert')).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(10_000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mocks.get).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId('operator-metadata-required-alert')).toBeInTheDocument();
  });
  it('keeps the card rendered when the server returns malformed metadata', async () => {
    mocks.get.mockResolvedValueOnce({});

    render(<OperatorMetadataComponent />);

    expect(await screen.findByTestId('operator-metadata-card')).toHaveAttribute('data-state', 'missing');
    expect(screen.getByLabelText('제품번호')).toHaveValue('');
    expect(screen.getByLabelText('금형 번호')).toHaveValue('');
    expect(screen.getByText('제품번호는 필수입니다.')).toBeInTheDocument();
    expect(screen.getByText('금형 번호는 필수입니다.')).toBeInTheDocument();
  });

  it('renders the previous three operator jobs in newest-first order', async () => {
    mocks.get.mockResolvedValueOnce(buildMetadata({
      product_no: '44444',
      operator_mold_no: '444',
      valid: true,
      missing_fields: [],
      updated_at: '2026-03-09T07:24:20Z',
      history: [
        { product_no: '33333', operator_mold_no: '333', updated_at: '2026-03-09T07:23:20Z' },
        { product_no: '22222', operator_mold_no: '222', updated_at: '2026-03-09T07:22:20Z' },
        { product_no: '11111', operator_mold_no: '111', updated_at: '2026-03-09T07:21:20Z' },
        { product_no: '00000', operator_mold_no: '000', updated_at: '2026-03-09T07:20:20Z' },
      ],
    }));

    render(<OperatorMetadataComponent />);

    const history = await screen.findByTestId('operator-metadata-history');
    expect(history).toHaveTextContent('이전 작업');
    expect(history).toHaveTextContent('33333, 333');
    expect(history).toHaveTextContent('22222, 222');
    expect(history).toHaveTextContent('11111, 111');
    expect(history).not.toHaveTextContent('00000, 000');
    expect(screen.queryByTestId('operator-metadata-guidance')).not.toBeInTheDocument();
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

  it('marks edited applied metadata as dirty until the operator applies it', async () => {
    mocks.get.mockResolvedValueOnce(buildMetadata({
      product_no: '12345',
      operator_mold_no: '123',
      valid: true,
      missing_fields: [],
      updated_at: '2026-03-09T07:20:20Z',
    }));
    render(<OperatorMetadataComponent />);

    const productInput = await screen.findByLabelText('제품번호');
    const applyButton = screen.getByTestId('operator-metadata-apply');

    expect(screen.getByTestId('operator-metadata-card')).toHaveAttribute('data-state', 'applied');
    expect(applyButton).not.toBeDisabled();
    expect(applyButton).toHaveAttribute('data-disabled', 'true');

    fireEvent.change(productInput, { target: { value: '67890' } });

    expect(screen.getByTestId('operator-metadata-card')).toHaveAttribute('data-state', 'dirty');
    expect(screen.queryByTestId('operator-metadata-guidance')).not.toBeInTheDocument();
    expect(screen.getByTestId('operator-metadata-history')).toBeInTheDocument();
    expect(applyButton).not.toHaveAttribute('data-disabled', 'true');
  });

  it('lets the operator mark a product change and confirm the current values', async () => {
    mocks.get.mockResolvedValueOnce(buildMetadata({
      product_no: '12345',
      operator_mold_no: '123',
      valid: true,
      missing_fields: [],
      updated_at: '2026-03-09T07:20:20Z',
    }));
    render(<OperatorMetadataComponent />);

    await screen.findByLabelText('제품번호');
    const card = screen.getByTestId('operator-metadata-card');
    const applyButton = screen.getByTestId('operator-metadata-apply');

    expect(card).toHaveAttribute('data-state', 'applied');
    expect(applyButton).not.toBeDisabled();
    expect(applyButton).toHaveAttribute('data-disabled', 'true');

    fireEvent.click(screen.getByTestId('operator-metadata-change-needed'));

    expect(card).toHaveAttribute('data-state', 'stale');
    expect(screen.queryByTestId('operator-metadata-guidance')).not.toBeInTheDocument();
    expect(screen.getByTestId('operator-metadata-history')).toBeInTheDocument();
    expect(applyButton).not.toHaveAttribute('data-disabled', 'true');

    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledWith({
        product_no: '12345',
        operator_mold_no: '123',
      });
    });
    await waitFor(() => {
      expect(card).toHaveAttribute('data-state', 'applied');
    });
  });

  it('keeps non-numeric product numbers client-side before save', async () => {
    render(<OperatorMetadataComponent />);

    const productInput = await screen.findByLabelText('제품번호');
    const moldInput = screen.getByLabelText('금형 번호');
    fireEvent.change(productInput, { target: { value: 'DW-12345' } });
    fireEvent.change(moldInput, { target: { value: '123' } });

    expect(screen.getByText('숫자만 입력할 수 있습니다.')).toBeInTheDocument();
    const applyButton = screen.getByTestId('operator-metadata-apply');
    expect(applyButton).not.toBeDisabled();
    expect(applyButton).toHaveAttribute('data-disabled', 'true');

    fireEvent.click(applyButton);

    expect(screen.queryByTestId('operator-metadata-required-alert')).not.toBeInTheDocument();
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('keeps non-numeric mold numbers client-side before save', async () => {
    render(<OperatorMetadataComponent />);

    const productInput = await screen.findByLabelText('제품번호');
    const moldInput = screen.getByLabelText('금형 번호');
    fireEvent.change(productInput, { target: { value: '12345' } });
    fireEvent.change(moldInput, { target: { value: '123-1' } });

    expect(screen.getByText('숫자만 입력할 수 있습니다.')).toBeInTheDocument();
    const applyButton = screen.getByTestId('operator-metadata-apply');
    expect(applyButton).not.toBeDisabled();
    expect(applyButton).toHaveAttribute('data-disabled', 'true');

    fireEvent.click(applyButton);

    expect(screen.queryByTestId('operator-metadata-required-alert')).not.toBeInTheDocument();
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('automatically refreshes clean fields when another client updates server metadata', async () => {
    vi.useFakeTimers();
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
        history: [
          { product_no: '11111', operator_mold_no: '111', updated_at: '2026-03-09T07:20:20Z' },
        ],
      }));
    render(<OperatorMetadataComponent />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    const [productInput, moldInput] = screen.getAllByRole('textbox');
    expect(productInput).toHaveValue('11111');
    expect(moldInput).toHaveValue('111');

    await act(async () => {
      vi.advanceTimersByTime(10_000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mocks.get).toHaveBeenCalledTimes(2);
    expect(productInput).toHaveValue('22222');
    expect(moldInput).toHaveValue('222');
    expect(screen.getByTestId('operator-metadata-history')).toHaveTextContent('11111, 111');
  });

  it('does not overwrite dirty local input during automatic server metadata refresh', async () => {
    vi.useFakeTimers();
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

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    const [productInput, moldInput] = screen.getAllByRole('textbox');
    fireEvent.change(productInput, { target: { value: '99999' } });

    await act(async () => {
      vi.advanceTimersByTime(10_000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mocks.get).toHaveBeenCalledTimes(2);
    expect(productInput).toHaveValue('99999');
    expect(moldInput).toHaveValue('111');
    expect(screen.getByTestId('operator-metadata-card')).toHaveAttribute('data-state', 'dirty');
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
    const applyButton = screen.getByTestId('operator-metadata-apply');
    expect(applyButton).not.toBeDisabled();
    expect(applyButton).toHaveAttribute('data-disabled', 'true');
    expect(screen.queryByTestId('operator-metadata-required-alert')).not.toBeInTheDocument();

    fireEvent.click(applyButton);

    expect(screen.getByTestId('operator-metadata-required-alert')).toHaveAttribute('data-alert-nonce', '1');
    expect(document.querySelectorAll('.operator-card-alert-ring')).toHaveLength(14);
    expect(mocks.update).not.toHaveBeenCalled();
  });
});
