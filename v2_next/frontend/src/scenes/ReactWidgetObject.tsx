import React, { useState, useEffect, useContext } from 'react';
import { SceneObjectBase, SceneObjectState, SceneComponentProps } from '@grafana/scenes';
import { LayoutEditContext } from '../LayoutEditContext';

export interface ReactWidgetState extends SceneObjectState {
  title?: string;
  type?: string;
  properties?: any;
  renderWidget: () => React.ReactNode;
}

export class ReactWidget extends SceneObjectBase<ReactWidgetState> {
  constructor(state: ReactWidgetState) {
    super(state);
  }

  static Component = ({ model }: SceneComponentProps<ReactWidget>) => {
    const { renderWidget, title } = model.useState();
    const { isEditing } = useContext(LayoutEditContext);
    const [titleEditing, setTitleEditing] = useState(false);
    const [tempTitle, setTempTitle] = useState(title || '');

    useEffect(() => {
      setTempTitle(title || '');
    }, [title]);

    const handleTitleClick = () => {
      if (isEditing) {
        setTitleEditing(true);
      }
    };

    const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setTempTitle(e.target.value);
    };

    const handleTitleBlur = () => {
      setTitleEditing(false);
      if (tempTitle !== title) {
        model.setState({ title: tempTitle });
      }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        (e.target as HTMLInputElement).blur();
      }
    };

    return (
      <div className="scene-react-widget" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
        {(title || (isEditing && titleEditing)) && (
          titleEditing ? (
             <input
               className="panel-header-input"
               value={tempTitle}
               onChange={handleTitleChange}
               onBlur={handleTitleBlur}
               onKeyDown={handleKeyDown}
               autoFocus
               style={{
                 width: '100%',
                 background: '#222',
                 border: '1px solid #444',
                 color: '#fff',
                 padding: '4px 8px',
                 fontSize: '14px',
                 height: '32px'
               }}
             />
          ) : (
            <div 
              className="panel-header grid-drag-handle-dashboard-grid"
              onClick={handleTitleClick}
              style={{ cursor: isEditing ? 'pointer' : 'default', border: isEditing ? '1px dashed #444' : 'none' }}
              title={isEditing ? "Click to edit title" : ""}
            >
               {title}
            </div>
          )
        )}
        <div className="panel-content" style={{ flex: 1, position: 'relative', overflow: 'visible' }}>
          {renderWidget()}
        </div>
      </div>
    );
  };
}
