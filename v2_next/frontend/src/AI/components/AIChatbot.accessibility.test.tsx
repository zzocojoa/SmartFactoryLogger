import React from 'react';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import type { RenderResult } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ModalContext } from '../../shared/context/GlobalModalContext';
import type { ModalContextType, ModalState } from '../../shared/types/GlobalModalContext.types';
import { AIChatbot } from './AIChatbot';
import { AIChatbotLauncher } from './AIChatbotLauncher';

vi.mock('../hooks/useAIAgent', () => ({
  useAIAgent: () => ({
    messages: [],
    isLoading: false,
    runningTool: null,
    apiKey: 'test-key',
    setApiKey: vi.fn(),
    model: 'gpt-4o-mini',
    updateModel: vi.fn(),
    sendMessage: vi.fn(),
    clearChat: vi.fn(),
  }),
}));

const buildModalState = (isOpen: boolean): ModalState => ({
  isOpen,
  type: 'alert',
  message: isOpen ? '진단 결과' : '',
  modalId: isOpen ? 1 : 0,
});

const buildModalContext = (isOpen: boolean): ModalContextType => ({
  alert: vi.fn<ModalContextType['alert']>(),
  confirm: vi.fn<ModalContextType['confirm']>(),
  prompt: vi.fn<ModalContextType['prompt']>(),
  close: vi.fn<ModalContextType['close']>(),
  state: buildModalState(isOpen),
});

const buildChatbotElement = (modalOpen: boolean): JSX.Element => (
  <ModalContext.Provider value={buildModalContext(modalOpen)}>
    <AIChatbot initialOpen={true} />
  </ModalContext.Provider>
);

const buildLauncherElement = (modalOpen: boolean): JSX.Element => (
  <ModalContext.Provider value={buildModalContext(modalOpen)}>
    <AIChatbotLauncher />
  </ModalContext.Provider>
);

const renderChatbot = (modalOpen: boolean): RenderResult => {
  return render(buildChatbotElement(modalOpen));
};

const renderLauncher = (modalOpen: boolean): RenderResult => {
  return render(buildLauncherElement(modalOpen));
};

describe('AIChatbot accessibility', () => {
  beforeEach(() => {
    HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
  });

  it('disables the launcher while a global modal is active', () => {
    const { rerender } = renderLauncher(false);

    expect(screen.getByRole('button', { name: 'AI 챗봇 열기' })).toBeEnabled();

    rerender(buildLauncherElement(true));

    expect(screen.getByRole('button', { name: 'AI 챗봇 열기 비활성화' })).toBeDisabled();
  });

  it('does not open the chat panel while a global modal is active', () => {
    renderChatbot(true);

    expect(screen.getByRole('button', { name: 'AI 챗봇 열기 비활성화' })).toBeDisabled();
    expect(screen.queryByText('SmartFactory Agent')).not.toBeInTheDocument();
  });

  it('closes the open chat panel when a global modal becomes active', async () => {
    const { rerender } = renderChatbot(false);

    expect(screen.getByText('SmartFactory Agent')).toBeInTheDocument();

    rerender(buildChatbotElement(true));

    await waitFor(() => {
      expect(screen.queryByText('SmartFactory Agent')).not.toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'AI 챗봇 열기 비활성화' })).toBeDisabled();
  });

  it('names icon-only controls when the chat panel is open', () => {
    renderChatbot(false);

    expect(screen.getByRole('button', { name: 'AI 챗봇 닫기' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'AI 챗봇 설정 열기' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'AI 챗봇 대화 지우기' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'AI 챗봇 메시지 보내기' })).toBeDisabled();
  });
});
