import { apiClient } from '../../shared/api/client';

export interface AIFunctionSchema {
  name: string;
  description: string;
  parameters: any;
}

export interface AIToolSchema {
  type: string;
  function: AIFunctionSchema;
}

export const fetchAITools = async (): Promise<AIToolSchema[]> => {
  try {
    const res = await apiClient.get('/ai/tools');
    return res.data.tools || [];
  } catch (error) {
    console.error('Failed to fetch AI tools from backend:', error);
    return [];
  }
};

export const invokeAITool = async (toolName: string, args: any): Promise<any> => {
  try {
    const res = await apiClient.post('/ai/invoke', {
      tool_name: toolName,
      arguments: args
    });
    return res.data.result;
  } catch (error) {
    console.error(`Failed to invoke AI tool ${toolName}:`, error);
    return { status: "error", message: `도구 실행 실패: ${error}` };
  }
};

export const callOpenAIChat = async (
  apiKey: string,
  model: string,
  messages: any[],
  tools: AIToolSchema[] | null
) => {
  const payload: any = {
    model: model || 'gpt-4o-mini',
    messages,
  };
  
  if (tools && tools.length > 0) {
    payload.tools = tools;
    payload.tool_choice = 'auto';
  }

  const res = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error?.message || `HTTP ${res.status}: OpenAI API fetch failed`);
  }

  return await res.json();
};
