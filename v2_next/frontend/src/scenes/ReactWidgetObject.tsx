import React from 'react';
import { SceneObjectBase, SceneObjectState, SceneComponentProps } from '@grafana/scenes';

export interface ReactWidgetState extends SceneObjectState {
  title?: string;
  renderWidget: () => React.ReactNode;
}

export class ReactWidget extends SceneObjectBase<ReactWidgetState> {
  constructor(state: ReactWidgetState) {
    super(state);
  }

  static Component = ({ model }: SceneComponentProps<ReactWidget>) => {
    const { renderWidget, title } = model.useState();

    return (
      <div className="scene-react-widget" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
        {title && (
          <div 
            className="panel-header grid-drag-handle-dashboard-grid" 
            style={{ 
              marginBottom: '8px', 
              fontWeight: 500, 
              cursor: 'grab', 
              background: '#f4f6f8',
              padding: '4px 8px' 
            }}
          >
             {title}
          </div>
        )}
        <div className="panel-content" style={{ flexGrow: 1, overflow: 'hidden' }}>
          {renderWidget()}
        </div>
      </div>
    );
  };
}
