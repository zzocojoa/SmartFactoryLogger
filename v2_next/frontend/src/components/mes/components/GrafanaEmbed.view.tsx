import React from 'react';
import type { GrafanaEmbedViewProps } from '../types/GrafanaEmbed.types';

export const GrafanaEmbedView: React.FC<GrafanaEmbedViewProps> = ({ dashboardUrl, title = 'Grafana Dashboard', model }) => {
  const { isLoading, hasError, resolvedHeight, hasDashboardUrl, handleLoad, handleError } = model;

  if (!hasDashboardUrl) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: resolvedHeight,
          background: 'var(--bg-card)',
          borderRadius: '8px',
          color: 'var(--text-secondary)',
          gap: '16px',
          padding: '32px',
        }}
      >
        <span style={{ fontSize: '48px' }}>📤</span>
        <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>Grafana Waiting for Connection</h3>
        <p style={{ margin: 0, textAlign: 'center', maxWidth: '400px' }}>
          Verify that local Grafana is running and dashboard URL is configured.
        </p>
        <div
          style={{
            background: 'var(--bg-main)',
            padding: '16px',
            borderRadius: '8px',
            fontSize: '14px',
            fontFamily: 'monospace',
          }}
        >
          <div style={{ color: 'var(--state-ok)' }}>$ docker run -d -p 3030:3000 grafana/grafana-oss</div>
          <div style={{ color: 'var(--text-muted)', marginTop: '8px' }}>or install and run Grafana OSS</div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        width: '100%',
        height: resolvedHeight,
        position: 'relative',
        borderRadius: '8px',
        overflow: 'hidden',
        background: 'var(--bg-card)',
      }}
    >
      {isLoading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--bg-card)',
            zIndex: 10,
          }}
        >
          <div className="spinner" style={{ width: '40px', height: '40px' }}></div>
          <span style={{ marginLeft: '12px', color: 'var(--text-secondary)' }}>Grafana loading...</span>
        </div>
      )}

      {hasError && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--bg-card)',
            color: 'var(--state-danger)',
            gap: '12px',
            zIndex: 10,
          }}
        >
          <span style={{ fontSize: '32px' }}>⚠️</span>
          <span>Grafana connection failed</span>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{dashboardUrl}</span>
        </div>
      )}

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
          display: hasError ? 'none' : 'block',
        }}
      />
    </div>
  );
};
