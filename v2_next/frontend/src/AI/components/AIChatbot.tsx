import React, { useState, useRef, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { MessageSquare, X, Send, Settings, Trash2, Bot, Wrench } from 'lucide-react';
import { useAIAgent } from '../hooks/useAIAgent';
import { ChatMessage } from './ChatMessage';

export const AIChatbot: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [input, setInput] = useState('');
  
  const { 
    messages, 
    isLoading, 
    runningTool, 
    apiKey, 
    setApiKey, 
    model, 
    updateModel, 
    sendMessage, 
    clearChat 
  } = useAIAgent();
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [tempKey, setTempKey] = useState(apiKey);
  const [tempModel, setTempModel] = useState(model);

  // Sync temp settings when dialog opens
  useEffect(() => {
    if (showSettings) {
      setTempKey(apiKey);
      setTempModel(model);
    }
  }, [showSettings, apiKey, model]);

  // Auto scroll
  useEffect(() => {
    if (messagesEndRef.current && isOpen) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading, runningTool, isOpen]);

  const handleSend = () => {
    if (!input.trim() || isLoading || !apiKey) return;
    sendMessage(input);
    setInput('');
  };
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const saveSettings = () => {
    setApiKey(tempKey);
    updateModel(tempModel);
    setShowSettings(false);
  };

  if (typeof document === 'undefined') return null;

  return ReactDOM.createPortal(
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col items-end pointer-events-none">
      {/* Floating Action Button */}
      <div className="pointer-events-auto">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={`w-14 h-14 rounded-full shadow-2xl flex items-center justify-center transition-all duration-300 ${
            isOpen 
              ? 'bg-gray-800 rotate-90 scale-90 text-gray-400' 
              : 'bg-gradient-to-r from-blue-600 to-cyan-500 hover:scale-105 hover:shadow-[0_0_20px_rgba(59,130,246,0.5)] text-white'
          }`}
        >
          {isOpen ? <X size={26} /> : <MessageSquare size={26} />}
        </button>
      </div>

      {/* Chat Window */}
      {isOpen && (
        <div className="absolute bottom-20 right-0 w-[420px] h-[650px] flex flex-col rounded-2xl overflow-hidden shadow-[0_10px_50px_rgba(0,0,0,0.5)] border border-white/10 bg-[#0A0D14]/90 backdrop-blur-3xl transform transition-all duration-300 origin-bottom-right pointer-events-auto">
          
          {/* Header */}
          <div className="h-16 flex items-center justify-between px-5 bg-gradient-to-r from-blue-900/50 to-indigo-900/50 border-b border-white/10">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center border border-blue-400/30">
                <Bot size={18} className="text-blue-400" />
              </div>
              <div>
                <h3 className="text-white font-semibold text-sm">SmartFactory Agent</h3>
                <p className="text-xs text-blue-300">Intelligent Data Assistant</p>
              </div>
            </div>
            <div className="flex space-x-2">
              <button 
                onClick={() => setShowSettings(!showSettings)}
                className={`p-2 rounded-lg transition-colors ${showSettings ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
              >
                <Settings size={18} />
              </button>
              <button 
                onClick={clearChat}
                title="대화 지우기"
                className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <Trash2 size={18} />
              </button>
            </div>
          </div>

          {/* Settings Panel */}
          {showSettings && (
            <div className="flex-1 bg-[#121620] p-6 overflow-y-auto">
              <h4 className="text-lg font-medium text-white mb-6">Agent Configuration</h4>
              
              <div className="space-y-5">
                <div>
                  <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wide">LLM Provider API Key</label>
                  <input 
                    type="password"
                    value={tempKey}
                    onChange={(e) => setTempKey(e.target.value)}
                    placeholder="sk-proj-..."
                    className="w-full bg-[#0A0D14] text-white px-4 py-3 rounded-xl border border-white/10 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors text-sm"
                  />
                  <p className="text-xs text-gray-500 mt-2">API 키는 브라우저 LocalStorage에만 안전하게 저장됩니다.</p>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wide">Model Selection</label>
                  <select
                    value={tempModel}
                    onChange={(e) => setTempModel(e.target.value)}
                    className="w-full bg-[#0A0D14] text-white px-4 py-3 rounded-xl border border-white/10 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors text-sm appearance-none"
                  >
                    <option value="gpt-4o-mini">OpenAI: GPT-4o-mini (권장, 빠름)</option>
                    <option value="gpt-4o">OpenAI: GPT-4o (고성능)</option>
                  </select>
                </div>
                
                <button 
                  onClick={saveSettings}
                  className="w-full mt-6 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white font-medium py-3 rounded-xl shadow-lg transition-all active:scale-[0.98]"
                >
                  Save & Apply
                </button>
              </div>
            </div>
          )}

          {/* Chat Messages Area */}
          {!showSettings && (
            <div className="flex-1 p-5 overflow-y-auto custom-scrollbar flex flex-col space-y-2">
              {messages.filter(m => m.role !== 'system').length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center opacity-50">
                  <Bot size={48} className="text-gray-500 mb-4" />
                  <p className="text-sm text-gray-400 text-center px-4">
                    환영합니다. SmartFactory의 현재 상태나 설비 데이터를 조회하려면 자연어로 질문해 보세요.
                  </p>
                </div>
              ) : (
                messages.map((msg, idx) => (
                  <ChatMessage key={idx} msg={msg} />
                ))
              )}
              
              {isLoading && !runningTool && (
                <div className="flex justify-start my-4">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center mr-3 shadow-lg ring-1 ring-white/10">
                    <Bot size={20} className="text-blue-400 animate-pulse" />
                  </div>
                  <div className="bg-[#181C26]/90 border border-white/10 rounded-2xl rounded-tl-md px-5 py-3.5 flex items-center space-x-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              )}
              
              {runningTool && (
                 <div className="flex justify-start my-4">
                    <div className="flex items-center text-xs text-[#00E676]/80 bg-[#00E676]/10 px-4 py-2 rounded-full border border-[#00E676]/20">
                        <Wrench className="w-4 h-4 mr-2 animate-spin-slow" />
                        백엔드 시스템 제어 중: <span className="font-mono ml-1 text-[#00E676]">{runningTool}</span>...
                    </div>
                 </div>
              )}
              
              <div ref={messagesEndRef} className="h-4" />
            </div>
          )}

          {/* Input Area */}
          {!showSettings && (
            <div className="p-4 bg-[#121620] border-t border-white/5">
              {!apiKey ? (
                <div className="text-center p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm cursor-pointer hover:bg-red-500/20 transition-colors"
                     onClick={() => setShowSettings(true)}>
                  ⚙️ API Key를 먼저 설정해주세요.
                </div>
              ) : (
                <div className="relative flex items-end bg-[#181C26] rounded-2xl border border-white/10 shadow-inner focus-within:ring-1 focus-within:ring-blue-500/50 focus-within:border-blue-500/50 transition-all">
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="명령을 입력하세요 (예: 현재 공장 온도 조회)"
                    className="w-full bg-transparent text-white px-5 py-4 min-h-[56px] max-h-[150px] resize-none focus:outline-none custom-scrollbar text-[14.5px]"
                    rows={1}
                    disabled={isLoading}
                  />
                  <button
                    onClick={handleSend}
                    disabled={!input.trim() || isLoading}
                    className="absolute right-2 bottom-2 p-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:hover:bg-blue-600 transition-colors text-white shadow-md active:scale-95 flex items-center justify-center m-1"
                  >
                    <Send size={18} className="translate-x-0.5" />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>,
    document.body
  );
};
