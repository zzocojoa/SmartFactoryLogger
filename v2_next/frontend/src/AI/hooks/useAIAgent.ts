import { useState, useCallback, useEffect } from 'react';
import { 
  fetchAITools, 
  invokeAITool, 
  callOpenAIChat, 
  AIToolSchema 
} from '../api/ai_service';

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string | null;
  name?: string;
  tool_call_id?: string;
  tool_calls?: any[];
}

export const useAIAgent = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [runningTool, setRunningTool] = useState<string | null>(null);
  const [tools, setTools] = useState<AIToolSchema[]>([]);
  
  // Try to load API key from local storage
  const [apiKey, setApiKeyState] = useState<string>(() => localStorage.getItem('ai_api_key') || '');
  const [model, setModel] = useState<string>(() => localStorage.getItem('ai_model') || 'gpt-4o-mini');

  const setApiKey = (key: string) => {
    localStorage.setItem('ai_api_key', key);
    setApiKeyState(key);
  };

  const updateModel = (m: string) => {
    localStorage.setItem('ai_model', m);
    setModel(m);
  }

  useEffect(() => {
    fetchAITools().then(setTools);
  }, []);

  // Set system prompt on init
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([{
        role: 'system',
        content: `당신은 SmartFactory 서버의 지능형 데이터 엔지니어 에이전트입니다. 
백엔드에서 제공하는 함수(도구)들을 적극적으로 활용하여 데이터 조회, 통신 설정, 시스템 관측, 메시지 동기화 등을 제어하세요.
가장 최신 정보를 기반으로 응답하며, 데이터를 표(Table)나 리스트, 마크다운 강조 기능을 사용하여 가독성 좋고 예쁜 리포트 형식으로 출력해야 합니다.`
      }]);
    }
  }, [messages.length]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || !apiKey) return;

    const userMessage: ChatMessage = { role: 'user', content: text };
    const newContext = [...messages, userMessage];
    setMessages(newContext);
    setIsLoading(true);

    let currentMessages = [...newContext];

    try {
      while (true) {
        // Send current context and tools to OpenAI
        const response = await callOpenAIChat(apiKey, model, currentMessages, tools.length > 0 ? tools : null);
        
        const responseMessage = response.choices[0].message;
        currentMessages.push(responseMessage);
        
        // No tool calls means the model produced a final text response.
        if (!responseMessage.tool_calls || responseMessage.tool_calls.length === 0) {
          setMessages(prev => {
            // Replace the last assistant message (which was "thinking") or append
            const temp = [...prev];
            if (temp.length > 0 && temp[temp.length - 1].role === 'assistant' && !temp[temp.length - 1].content) {
              temp.pop();
            }
            return [...temp, responseMessage];
          });
          break;
        }

        // Display "assistant is thinking/calling tools" in the UI sequence
        setMessages(prev => {
          const temp = [...prev];
          if (temp.length > 0 && temp[temp.length - 1].role === 'assistant' && !temp[temp.length - 1].content) {
            temp.pop();
          }
          return [...temp, responseMessage];
        }); 
        
        for (const toolCall of responseMessage.tool_calls) {
          if (toolCall.type === 'function') {
            const funcName = toolCall.function.name;
            const funcArgs = JSON.parse(toolCall.function.arguments || '{}');
            
            setRunningTool(funcName);
            
            // Execute real API locally against the backend
            const result = await invokeAITool(funcName, funcArgs);
            
            // Append result as tool message to context array
            currentMessages.push({
              tool_call_id: toolCall.id,
              role: 'tool',
              name: funcName,
              content: JSON.stringify(result)
            });
            
            setRunningTool(null);
          }
        }
        
        // Loop automatically continues to pass these tool results to OpenAI for its next completion layer...
      }
    } catch (err: any) {
      console.error(err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `❌ 오류가 발생했습니다: ${err.message}`
      }]);
    } finally {
      setIsLoading(false);
      setRunningTool(null);
    }
  }, [apiKey, model, messages, tools]);

  const clearChat = () => {
     setMessages([]); // Set to empty to retrigger the system prompt effect
  };

  return {
    messages,
    isLoading,
    runningTool,
    apiKey,
    setApiKey,
    model,
    updateModel,
    sendMessage,
    clearChat
  };
};
