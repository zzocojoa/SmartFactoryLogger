import React from 'react';

interface StatsWidgetProps {
    title: string;
    value: string | number;
    icon?: React.ReactNode;
    color?: string;
    subText?: string;
}

export const StatsWidget: React.FC<StatsWidgetProps> = ({ 
    title, 
    value, 
    icon, 
    color = 'var(--accent-main)',
    subText
}) => {
    return (
        <div style={{
            background: 'rgba(255, 255, 255, 0.03)',
            backdropFilter: 'blur(10px)',
            borderRadius: 'var(--card-radius)',
            padding: '1rem 1.25rem',
            border: '1px solid var(--border-color)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.5rem',
            minWidth: '200px',
            flex: 1,
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
            transition: 'transform 0.2s',
            cursor: 'default'
        }}
        onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
        onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
        >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ 
                    fontSize: '0.85rem', 
                    color: 'var(--text-secondary)', 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px' 
                }}>
                    {title}
                </span>
                {icon && (
                    <div style={{ 
                        color: color,
                        background: `color-mix(in srgb, ${color} 15%, transparent)`,
                        padding: '6px',
                        borderRadius: '6px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}>
                        {icon}
                    </div>
                )}
            </div>
            
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
                <span style={{ 
                    fontSize: '1.75rem', 
                    fontWeight: 700, 
                    color: 'var(--text-primary)' 
                }}>
                    {value}
                </span>
                {subText && (
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {subText}
                    </span>
                )}
            </div>
            
            {/* Decoration Bar */}
            <div style={{ 
                height: '3px', 
                width: '100%', 
                background: `color-mix(in srgb, ${color} 20%, transparent)`, 
                borderRadius: '2px',
                marginTop: 'auto'
            }}>
                <div style={{ 
                    height: '100%', 
                    width: '60%', 
                    background: color, 
                    borderRadius: '2px' 
                }} />
            </div>
        </div>
    );
};
