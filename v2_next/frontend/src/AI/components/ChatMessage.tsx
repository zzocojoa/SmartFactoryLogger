import React from 'react';
import ReactMarkdown from 'react-markdown';
import User from 'lucide-react/dist/esm/icons/user';
import Bot from 'lucide-react/dist/esm/icons/bot';
import Wrench from 'lucide-react/dist/esm/icons/wrench';
import { ChatMessage as MessageType } from '../hooks/useAIAgent';

export const ChatMessage: React.FC<{ msg: MessageType }> = ({ msg }) => {
  // Hide raw system instructions
  if (msg.role === 'system') return null;

  // Handle Tool Calling intermediate states
  if (msg.role === 'tool' || (msg.role === 'assistant' && msg.tool_calls && !msg.content)) {
    return (
      <div className="flex justify-start my-3">
         <div className="flex items-center text-xs text-[#00E676]/70 bg-[#00E676]/10 px-3 py-1.5 rounded-full border border-[#00E676]/20">
             <Wrench className="w-3.5 h-3.5 mr-1.5 animate-pulse" />
             {msg.tool_calls 
                ? `도구 실행 중...` 
                : `[${msg.name}] 데이터 시스템 반환 완료`}
         </div>
      </div>
    );
  }

  const isUser = msg.role === 'user';
  
  return (
    <div className={`flex w-full my-4 group ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="w-9 h-9 flex-shrink-0 rounded-xl bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center mr-3 shadow-lg ring-1 ring-white/10 mt-1">
            <Bot size={20} className="text-blue-400" />
        </div>
      )}
      
      <div className={`max-w-[80%] rounded-2xl px-4 py-3 shadow-md ${
        isUser 
          ? 'bg-gradient-to-br from-blue-600 to-blue-700 text-white rounded-tr-md ring-1 ring-blue-500/50' 
          : 'bg-[#181C26]/90 text-[#E0E6ED] border border-white/10 rounded-tl-md backdrop-blur-xl shadow-[0_4px_30px_rgba(0,0,0,0.5)]'
      }`}>
        {isUser ? (
          <p className="text-[14.5px] font-medium leading-relaxed whitespace-pre-wrap">{msg.content}</p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none text-[14.5px] leading-relaxed 
                          prose-th:bg-gray-800/50 prose-th:p-2 prose-td:p-2 prose-tr:border-b prose-tr:border-gray-700/50
                          prose-table:overflow-hidden prose-table:rounded-lg prose-table:border prose-table:border-gray-700/50">
            <ReactMarkdown>{msg.content || ''}</ReactMarkdown>
          </div>
        )}
      </div>

      {isUser && (
         <div className="w-9 h-9 flex-shrink-0 rounded-xl bg-gradient-to-br from-gray-700 to-gray-800 flex items-center justify-center ml-3 shadow-lg ring-1 ring-white/10 mt-1">
            <User size={20} className="text-gray-300" />
         </div>
      )}
    </div>
  );
};
