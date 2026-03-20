import type { ChatMessage } from '../hooks/useAIAgent';

export interface AIDiagnosticsSnapshot {
  messageCount: number;
  toolCount: number;
  estimatedBytes: number;
}

let currentSnapshot: AIDiagnosticsSnapshot = {
  messageCount: 0,
  toolCount: 0,
  estimatedBytes: 0,
};

const estimateStringBytes = (value: string | null | undefined): number => {
  if (!value) {
    return 0;
  }
  return value.length * 2;
};

const estimateMessagesBytes = (messages: ChatMessage[]): number => {
  return messages.reduce((total, item) => {
    const toolCalls = Array.isArray(item.tool_calls) ? JSON.stringify(item.tool_calls).length * 2 : 0;
    return (
      total +
      estimateStringBytes(item.role) +
      estimateStringBytes(item.content) +
      estimateStringBytes(item.name) +
      estimateStringBytes(item.tool_call_id) +
      toolCalls
    );
  }, 0);
};

export const updateAIDiagnostics = (messages: ChatMessage[], toolCount: number): void => {
  currentSnapshot = {
    messageCount: messages.length,
    toolCount,
    estimatedBytes: estimateMessagesBytes(messages),
  };
};

export const getAIDiagnostics = (): AIDiagnosticsSnapshot => currentSnapshot;
