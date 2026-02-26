import React, { useState, useEffect, useMemo } from 'react';
import X from 'lucide-react/dist/esm/icons/x';
import Calendar from 'lucide-react/dist/esm/icons/calendar';
import RefreshCw from 'lucide-react/dist/esm/icons/refresh-cw';
import AlertTriangle from 'lucide-react/dist/esm/icons/alert-triangle';
import Loader2 from 'lucide-react/dist/esm/icons/loader-2';
import Calculator from 'lucide-react/dist/esm/icons/calculator';
import Settings from 'lucide-react/dist/esm/icons/settings';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'general' | 'sync'>('sync');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Initialize dates with last 3 days
  useEffect(() => {
    if (isOpen) {
      const today = new Date();
      const threeDaysAgo = new Date();
      threeDaysAgo.setDate(today.getDate() - 3);
      
      setEndDate(today.toISOString().split('T')[0]);
      setStartDate(threeDaysAgo.toISOString().split('T')[0]);
      
      // Check status immediately
      fetchStatus();
    }
  }, [isOpen]);

  // Poll status while syncing
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isOpen && isSyncing) {
      interval = setInterval(fetchStatus, 2000);
    }
    return () => clearInterval(interval);
  }, [isOpen, isSyncing]);

  // Keyboard shortcuts: Esc to close, Enter to start sync
  useEffect(() => {
    if (!isOpen) return;
    
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'Enter' && !isSyncing && startDate && endDate) {
        e.preventDefault();
        handleStartSync();
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isSyncing, startDate, endDate, onClose]);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`/api/mes/sync/status`);
      const data = await res.json();
      setSyncStatus(data);
      if (data.status === 'running') {
        setIsSyncing(true);
      } else if (data.status === 'completed' || data.status === 'error') {
        setIsSyncing(false);
      }
    } catch (e) {
      console.error("Failed to fetch sync status", e);
    }
  };

  const handleStartSync = async () => {
    if (!startDate || !endDate) {
      setError("Please select both start and end dates.");
      return;
    }
    setError(null);
    setIsSyncing(true);
    
    try {
      const res = await fetch(`/api/mes/sync/manual`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from_date: startDate, to_date: endDate })
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start sync");
      }
      
      // Trigger status fetch immediately
      fetchStatus();
      
    } catch (e: any) {
        setError(e.message);
        setIsSyncing(false);
    }
  };

  // Calculate estimated workload
  const PAGE_COUNT = 12; // MES pages count
  const estimatedCount = useMemo(() => {
    if (!startDate || !endDate) return 0;
    const start = new Date(startDate);
    const end = new Date(endDate);
    const diffTime = end.getTime() - start.getTime();
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24)) + 1;
    return diffDays > 0 ? diffDays * PAGE_COUNT : 0;
  }, [startDate, endDate]);

  // Check if date range is 7+ days
  const isLongDuration = useMemo(() => {
    if (!startDate || !endDate) return false;
    const start = new Date(startDate);
    const end = new Date(endDate);
    const diffTime = end.getTime() - start.getTime();
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24)) + 1;
    return diffDays >= 7;
  }, [startDate, endDate]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-[700px] bg-[#1a1c23] border border-white/10 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="h-14 border-b border-white/10 flex items-center justify-between px-6 bg-gradient-to-r from-[#0F1117] to-[#1A1D24]">
          <div className="flex items-center gap-3">
            <Settings size={20} className="text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">설정</h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg transition-colors text-gray-400 hover:text-white">
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 min-h-[400px]">
          {/* Sidebar */}
          <div className="w-48 border-r border-white/10 bg-black/30 p-4 space-y-2">
            <button
              onClick={() => setActiveTab('general')}
              className={`w-full text-left px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'general' 
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30' 
                  : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
              }`}
            >
              일반
            </button>
            <button
              onClick={() => setActiveTab('sync')}
              className={`w-full text-left px-4 py-3 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                activeTab === 'sync' 
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30' 
                  : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
              }`}
            >
              <RefreshCw size={16} />
              데이터 동기화
            </button>
          </div>

          {/* Main Area */}
          <div className="flex-1 p-6 overflow-y-auto">
            {activeTab === 'sync' && (
              <div className="space-y-8 animate-in slide-in-from-right-4 duration-300">
                
                <div>
                  <h3 className="text-xl font-bold text-white mb-2">수동 데이터 동기화</h3>
                  <p className="text-gray-400 text-sm">
                    수동으로 제조 데이터를 수집하고 동기화합니다.
                  </p>
                </div>

                <div className="bg-white/5 border border-white/10 rounded-xl p-6 space-y-6">
                  
                  {/* Quick Select Buttons */}
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider">최근 선택</label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          const today = new Date();
                          const start = new Date();
                          start.setDate(today.getDate() - 3);
                          setStartDate(start.toISOString().split('T')[0]);
                          setEndDate(today.toISOString().split('T')[0]);
                        }}
                        disabled={isSyncing}
                        className="flex-1 py-2.5 px-4 rounded-full text-sm font-medium transition-all bg-white/5 border border-white/10 text-gray-300 hover:bg-cyan-500/20 hover:border-cyan-400/50 hover:text-cyan-300 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        최근 3일
                      </button>
                      <button
                        onClick={() => {
                          const today = new Date();
                          const start = new Date();
                          start.setDate(today.getDate() - 7);
                          setStartDate(start.toISOString().split('T')[0]);
                          setEndDate(today.toISOString().split('T')[0]);
                        }}
                        disabled={isSyncing}
                        className="flex-1 py-2.5 px-4 rounded-full text-sm font-medium transition-all bg-white/5 border border-white/10 text-gray-300 hover:bg-cyan-500/20 hover:border-cyan-400/50 hover:text-cyan-300 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        최근 7일
                      </button>
                      <button
                        onClick={() => {
                          const today = new Date();
                          const start = new Date(today.getFullYear(), today.getMonth(), 1);
                          setStartDate(start.toISOString().split('T')[0]);
                          setEndDate(today.toISOString().split('T')[0]);
                        }}
                        disabled={isSyncing}
                        className="flex-1 py-2.5 px-4 rounded-full text-sm font-medium transition-all bg-white/5 border border-white/10 text-gray-300 hover:bg-cyan-500/20 hover:border-cyan-400/50 hover:text-cyan-300 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        이번 달
                      </button>
                    </div>
                  </div>
                  
                  {/* Date Range Selector - Mockup style */}
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider">날짜 범위 선택</label>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs text-gray-500">시작일</span>
                        <input
                          type="date"
                          value={startDate}
                          onChange={(e) => setStartDate(e.target.value)}
                          className="w-full bg-black/40 border border-white/10 rounded-lg py-2.5 pl-14 pr-3 text-sm text-gray-200 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 transition-all calendar-picker-indicator-white"
                          disabled={isSyncing}
                        />
                      </div>
                      <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs text-gray-500">종료일</span>
                        <input
                          type="date"
                          value={endDate}
                          onChange={(e) => setEndDate(e.target.value)}
                          className="w-full bg-black/40 border border-white/10 rounded-lg py-2.5 pl-14 pr-3 text-sm text-gray-200 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 transition-all calendar-picker-indicator-white"
                          disabled={isSyncing}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Estimated Workload Display - Mockup style */}
                  {estimatedCount > 0 && (
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-gray-400">예상 워크로드</span>
                      <span className="px-3 py-1 rounded-full bg-cyan-500/20 text-cyan-300 text-sm font-semibold border border-cyan-500/30">
                        ≈ {estimatedCount}건 예상
                      </span>
                    </div>
                  )}

                  {/* Long Duration Warning */}
                  {isLongDuration && !isSyncing && (
                    <div className="flex items-start gap-3 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3">
                      <AlertTriangle size={16} className="text-amber-400 mt-0.5 shrink-0" />
                      <p className="text-sm text-amber-300">
                        7일 이상의 데이터 수집은 <span className="font-semibold">시간이 오래 걸릴 수 있습니다.</span>
                        <br />
                        <span className="text-amber-400/70 text-xs">네트워크 상태에 따라 10분 이상 소요될 수 있습니다.</span>
                      </p>
                    </div>
                  )}

                  {error && (
                    <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-red-400 text-sm">
                      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                      <p>{error}</p>
                    </div>
                  )}

                  <div className="pt-2">
                    <button
                      onClick={handleStartSync}
                      disabled={isSyncing}
                      className={`w-full py-3 rounded-lg font-semibold flex items-center justify-center gap-2 transition-all ${
                        isSyncing 
                          ? 'bg-cyan-500/20 text-cyan-400 cursor-not-allowed border border-cyan-500/30'
                          : 'bg-gradient-to-r from-cyan-600 to-teal-500 hover:from-cyan-500 hover:to-teal-400 text-white shadow-lg shadow-cyan-500/20'
                      }`}
                    >
                      {isSyncing ? (
                        <>
                          <Loader2 size={18} className="animate-spin" />
                          수집 중...
                        </>
                      ) : (
                        <>
                          <RefreshCw size={18} />
                          수집 시작
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Status Monitor */}
                {syncStatus && (syncStatus.status !== 'idle' || isSyncing) && (
                  <div className="space-y-4">
                    {/* Step Indicator */}
                    <div className="flex items-center justify-between">
                      {['login', 'collecting', 'saving', 'done'].map((step, idx) => {
                        const steps = ['login', 'collecting', 'saving', 'done'];
                        const labels = ['로그인', '수집', '저장', '완료'];
                        const currentIdx = steps.indexOf(syncStatus.current_step || 'idle');
                        const isActive = idx === currentIdx;
                        const isCompleted = idx < currentIdx;
                        
                        return (
                          <div key={step} className="flex items-center">
                            <div className="flex flex-col items-center">
                              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                                isCompleted ? 'bg-emerald-500 text-white' :
                                isActive ? 'bg-blue-500 text-white animate-pulse' :
                                'bg-white/10 text-gray-500'
                              }`}>
                                {isCompleted ? '✓' : idx + 1}
                              </div>
                              <span className={`text-xs mt-1 ${
                                isCompleted ? 'text-emerald-400' :
                                isActive ? 'text-blue-400' : 'text-gray-500'
                              }`}>{labels[idx]}</span>
                            </div>
                            {idx < 3 && (
                              <div className={`w-12 h-0.5 mx-1 ${
                                idx < currentIdx ? 'bg-emerald-500' : 'bg-white/10'
                              }`} />
                            )}
                          </div>
                        );
                      })}
                    </div>
                    
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-400">진행 상황</span>
                      <span className={`font-medium ${
                        syncStatus.status === 'completed' ? 'text-emerald-400' :
                        syncStatus.status === 'error' ? 'text-red-400' : 'text-blue-400'
                      }`}>
                         {syncStatus.current_date ? `${syncStatus.current_date}` : syncStatus.status.toUpperCase()}
                         {syncStatus.total > 0 && ` (${Math.round((syncStatus.progress / syncStatus.total) * 100)}%)`}
                      </span>
                    </div>
                    
                    <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                      <div 
                        className={`h-full transition-all duration-500 ${
                           syncStatus.status === 'completed' ? 'bg-emerald-500' :
                           syncStatus.status === 'error' ? 'bg-red-500' : 'bg-blue-500'
                        }`}
                        style={{ width: `${(syncStatus.progress / Math.max(syncStatus.total, 1)) * 100}%` }}
                      />
                    </div>
                    
                    <p className="text-xs text-center text-gray-500 font-mono">
                      {syncStatus.message}
                    </p>
                  </div>
                )}

                {/* Completion Summary Card */}
                {syncStatus?.status === 'completed' && syncStatus?.result && (
                  <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-4 space-y-3">
                    <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                        <polyline points="22 4 12 14.01 9 11.01" />
                      </svg>
                      수집 완료
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-center">
                      <div>
                        <div className="text-2xl font-bold text-white">{syncStatus.result.total_collected}</div>
                        <div className="text-xs text-gray-400">총 수집 건수</div>
                      </div>
                      <div>
                        <div className="text-2xl font-bold text-white">{syncStatus.result.elapsed_time}</div>
                        <div className="text-xs text-gray-400">소요 시간</div>
                      </div>
                      <div>
                        <div className={`text-2xl font-bold ${syncStatus.result.errors?.length > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                          {syncStatus.result.errors?.length || 0}
                        </div>
                        <div className="text-xs text-gray-400">에러 수</div>
                      </div>
                    </div>
                    {syncStatus.result.errors?.length > 0 && (
                      <details className="text-xs">
                        <summary className="text-amber-400 cursor-pointer hover:text-amber-300">에러 상세 보기</summary>
                        <ul className="mt-2 space-y-1 text-gray-400 max-h-24 overflow-y-auto">
                          {syncStatus.result.errors.slice(0, 5).map((err: string, i: number) => (
                            <li key={i} className="truncate">• {err}</li>
                          ))}
                          {syncStatus.result.errors.length > 5 && (
                            <li className="text-gray-500">...외 {syncStatus.result.errors.length - 5}건</li>
                          )}
                        </ul>
                      </details>
                    )}
                  </div>
                )}

              </div>
            )}

            {activeTab === 'general' && (
              <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-4">
                 <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center">
                    <Settings size={32} className="text-gray-600" />
                 </div>
                 <p>일반 설정은 준비 중입니다.</p>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};
