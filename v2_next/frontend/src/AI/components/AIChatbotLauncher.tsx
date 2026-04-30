import React, { Suspense, useState } from 'react';
import ReactDOM from 'react-dom';
import MessageSquare from 'lucide-react/dist/esm/icons/message-square';

const AIChatbot = React.lazy(() => import('./AIChatbot').then(m => ({ default: m.AIChatbot })));

const ChatbotLoadingButton = (): JSX.Element => {
  return ReactDOM.createPortal(
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col items-end pointer-events-none">
      <div className="pointer-events-auto">
        <button
          className="w-14 h-14 rounded-full shadow-2xl flex items-center justify-center transition-all duration-300 bg-gradient-to-r from-blue-600 to-cyan-500 text-white opacity-70"
          disabled
          aria-label={'AI \uCC57\uBD07 \uB85C\uB529 \uC911'}
        >
          <MessageSquare size={26} />
        </button>
      </div>
    </div>,
    document.body
  );
};

export const AIChatbotLauncher = (): JSX.Element | null => {
  const [enabled, setEnabled] = useState(false);

  if (typeof document === 'undefined') {
    return null;
  }

  if (enabled) {
    return (
      <Suspense fallback={<ChatbotLoadingButton />}>
        <AIChatbot initialOpen={true} />
      </Suspense>
    );
  }

  return ReactDOM.createPortal(
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col items-end pointer-events-none">
      <div className="pointer-events-auto">
        <button
          onClick={() => setEnabled(true)}
          className="w-14 h-14 rounded-full shadow-2xl flex items-center justify-center transition-all duration-300 bg-gradient-to-r from-blue-600 to-cyan-500 hover:scale-105 hover:shadow-[0_0_20px_rgba(59,130,246,0.5)] text-white"
          aria-label={'AI \uCC57\uBD07 \uC5F4\uAE30'}
        >
          <MessageSquare size={26} />
        </button>
      </div>
    </div>,
    document.body
  );
};
