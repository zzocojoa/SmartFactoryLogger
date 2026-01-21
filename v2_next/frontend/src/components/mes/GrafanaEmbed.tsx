import React, { useState } from 'react';

interface GrafanaEmbedProps {
    /**
     * Full URL to the Grafana dashboard.
     * Example: http://localhost:3030/d/abc123/my-dashboard?orgId=1&kiosk
     */
    dashboardUrl: string;
    
    /**
     * Height of the iframe. Default: 100%
     */
    height?: string | number;
    
    /**
     * Optional title for the embed
     */
    title?: string;
}

/**
 * Component to embed a Grafana dashboard via iframe.
 * 
 * Prerequisites:
 * 1. Grafana must be running locally (default: http://localhost:3030)
 * 2. grafana.ini must have:
 *    - [security] allow_embedding = true
 *    - [auth.anonymous] enabled = true
 * 3. Use ?kiosk parameter to hide Grafana's header/sidebar
 */
export const GrafanaEmbed: React.FC<GrafanaEmbedProps> = ({
    dashboardUrl,
    height = '100%',
    title = 'Grafana Dashboard'
}) => {
    const [isLoading, setIsLoading] = useState(true);
    const [hasError, setHasError] = useState(false);

    const handleLoad = () => {
        setIsLoading(false);
    };

    const handleError = () => {
        setIsLoading(false);
        setHasError(true);
    };

    // Default placeholder if no URL provided
    if (!dashboardUrl) {
        return (
            <div style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: typeof height === 'number' ? `${height}px` : height,
                background: 'var(--bg-card)',
                borderRadius: '8px',
                color: 'var(--text-secondary)',
                gap: '16px',
                padding: '32px'
            }}>
                <span style={{ fontSize: '48px' }}>📊</span>
                <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>Grafana 연동 대기 중</h3>
                <p style={{ margin: 0, textAlign: 'center', maxWidth: '400px' }}>
                    로컬 Grafana가 실행 중이지 않거나, 대시보드 URL이 설정되지 않았습니다.
                </p>
                <div style={{ 
                    background: 'var(--bg-main)', 
                    padding: '16px', 
                    borderRadius: '8px',
                    fontSize: '14px',
                    fontFamily: 'monospace'
                }}>
                    <div style={{ color: 'var(--state-ok)' }}>$ docker run -d -p 3030:3000 grafana/grafana-oss</div>
                    <div style={{ color: 'var(--text-muted)', marginTop: '8px' }}>또는 Grafana OSS 설치 후 실행</div>
                </div>
            </div>
        );
    }

    return (
        <div style={{ 
            width: '100%', 
            height: typeof height === 'number' ? `${height}px` : height,
            position: 'relative',
            borderRadius: '8px',
            overflow: 'hidden',
            background: 'var(--bg-card)'
        }}>
            {/* Loading Overlay */}
            {isLoading && (
                <div style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'var(--bg-card)',
                    zIndex: 10
                }}>
                    <div className="spinner" style={{ width: '40px', height: '40px' }}></div>
                    <span style={{ marginLeft: '12px', color: 'var(--text-secondary)' }}>
                        Grafana 로딩 중...
                    </span>
                </div>
            )}

            {/* Error State */}
            {hasError && (
                <div style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'var(--bg-card)',
                    color: 'var(--state-danger)',
                    gap: '12px',
                    zIndex: 10
                }}>
                    <span style={{ fontSize: '32px' }}>⚠️</span>
                    <span>Grafana 연결 실패</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        {dashboardUrl}
                    </span>
                </div>
            )}

            {/* Grafana iframe */}
            <iframe
                src={dashboardUrl}
                title={title}
                width="100%"
                height="100%"
                frameBorder="0"
                onLoad={handleLoad}
                onError={handleError}
                style={{
                    border: 'none',
                    display: hasError ? 'none' : 'block'
                }}
            />
        </div>
    );
};

export default GrafanaEmbed;
