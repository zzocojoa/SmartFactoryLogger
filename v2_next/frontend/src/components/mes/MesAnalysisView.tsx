import React, { useMemo } from 'react';
import { EmbeddedScene } from '@grafana/scenes';
import { getMesAnalysisScene } from '../../scenes/MesAnalysisScene';

interface MesAnalysisViewProps {
    data: any[];
    pageKey: string | null;
}

export const MesAnalysisView: React.FC<MesAnalysisViewProps> = ({ data, pageKey }) => {
    // Re-create scene when data or pageKey changes to update widgets
    const scene = useMemo(() => {
        return getMesAnalysisScene(data, pageKey);
    }, [data, pageKey]);

    return (
        <div style={{ width: '100%', height: '100%', padding: '16px', overflow: 'auto' }}>
           <scene.Component model={scene} />
        </div>
    );
};
