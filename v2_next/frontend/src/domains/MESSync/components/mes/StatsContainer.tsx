import { detectDateColumn } from '../../../../shared/utils/dataGridUtils';
import React, { useMemo } from 'react';
import { StatsWidget } from './StatsWidget';

const ListIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="8" y1="6" x2="21" y2="6"></line>
        <line x1="8" y1="12" x2="21" y2="12"></line>
        <line x1="8" y1="18" x2="21" y2="18"></line>
        <line x1="3" y1="6" x2="3.01" y2="6"></line>
        <line x1="3" y1="12" x2="3.01" y2="12"></line>
        <line x1="3" y1="18" x2="3.01" y2="18"></line>
    </svg>
);

const TimeIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <polyline points="12 6 12 12 16 14"></polyline>
    </svg>
);

const CheckIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
        <polyline points="22 4 12 14.01 9 11.01"></polyline>
    </svg>
);

const AlertIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
    </svg>
);

interface StatsContainerProps {
    data: any[];
}

export const StatsContainer: React.FC<StatsContainerProps> = ({ data }) => {
    const stats = useMemo(() => {
        if (!data || data.length === 0) {
            return { total: 0, todayCount: 0, okCount: 0, ngCount: 0, hasStatus: false };
        }

        const total = data.length;
        
        // Auto-detect date column
        const sample = data[0];
        const dateCol = detectDateColumn(sample);
        
        // Calculate today's count
        const today = new Date();
        const todayStr = today.toLocaleDateString('en-CA'); // YYYY-MM-DD format (local time)
        
        const todayCount = dateCol 
            ? data.filter(item => {
                const val = item[dateCol];
                if (!val) return false;
                
                // If value is a full timestamp (e.g. 2026-01-16T...), extract just the date part
                const dateValStr = String(val).substring(0, 10);
                return dateValStr === todayStr;
            }).length
            : 0;

        // Auto-detect status column
        const statusKey = Object.keys(sample).find(k => 
            ['status', 'result', 'judgment', 'judge', 'quality', 'state'].includes(k.toLowerCase())
        );

        let okCount = 0;
        let ngCount = 0;

        if (statusKey) {
            data.forEach(item => {
                const val = String(item[statusKey] || '').toUpperCase();
                if (['OK', 'PASS', 'NORMAL', 'GOOD'].some(s => val.includes(s))) okCount++;
                else if (['NG', 'FAIL', 'ERROR', 'BAD'].some(s => val.includes(s))) ngCount++;
            });
        }

        return { total, todayCount, okCount, ngCount, hasStatus: !!statusKey };
    }, [data]);

    return (
        <div style={{ 
            display: 'flex', 
            gap: '1rem', 
            padding: '1rem',
            paddingBottom: '0.5rem',
            flexWrap: 'wrap'
        }}>
            <StatsWidget 
                title="Total Records" 
                value={stats.total.toLocaleString()} 
                icon={<ListIcon />}
                color="var(--primary-main)"
            />
            <StatsWidget 
                title="Today's Data" 
                value={stats.todayCount.toLocaleString()} 
                icon={<TimeIcon />}
                color="var(--info-main)"
                subText="records"
            />
            {stats.hasStatus && (
                <>
                    <StatsWidget 
                        title="OK Count" 
                        value={stats.okCount.toLocaleString()} 
                        icon={<CheckIcon />}
                        color="var(--success-main)"
                    />
                    <StatsWidget 
                        title="NG Count" 
                        value={stats.ngCount.toLocaleString()} 
                        icon={<AlertIcon />}
                        color="var(--error-main)"
                    />
                </>
            )}
        </div>
    );
};
