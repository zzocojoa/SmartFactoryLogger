import React from 'react';
import {
  EmbeddedScene,
  SceneGridLayout,
  SceneGridItem,
} from '@grafana/scenes';
import { ReactWidget } from './ReactWidgetObject';
import { StatsContainer } from '../components/mes/StatsContainer';
import { ProductivityChart } from '../components/mes/ProductivityChart';

export function getMesAnalysisScene(data: any[], pageKey: string | null) {
  return new EmbeddedScene({
    body: new SceneGridLayout({
      key: 'mes-analysis-grid',
      isDraggable: true,
      isResizable: true,
      children: [
        // Top Row: Stats Container (Full Width)
        new SceneGridItem({
          key: 'stats-widget',
          x: 0,
          y: 0,
          width: 24, // Full width (assuming 24 cols setup)
          height: 6,
          body: new ReactWidget({
            key: 'stats-widget-body',
            title: '종합 현황',
            type: 'stats',
            renderWidget: () => (
              <div className="card" style={{ width: '100%', height: '100%' }}>
                <StatsContainer data={data} />
              </div>
            )
          })
        }),
        // Middle Row: Productivity Chart (Full Width)
        new SceneGridItem({
          key: 'productivity-chart-widget',
          x: 0,
          y: 6,
          width: 24,
          height: 12,
          body: new ReactWidget({
            key: 'chart-widget-body',
            title: '생산성 분석',
            type: 'chart',
            renderWidget: () => (
              <div className="card" style={{ width: '100%', height: '100%', minHeight: '300px' }}>
                <ProductivityChart data={data} pageKey={'rpt_press'} />
              </div>
            )
          })
        }),
      ],
    }),
  });
}
