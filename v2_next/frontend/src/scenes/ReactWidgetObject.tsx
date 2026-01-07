import React, { useState, useEffect, useContext } from 'react';
import { SceneObjectBase, SceneObjectState, SceneComponentProps } from '@grafana/scenes';
import { LayoutEditContext } from '../LayoutEditContext';

export interface ReactWidgetState extends SceneObjectState {
  title?: string;
  type?: string;
  isContentEditing?: boolean;
  properties?: any;
  renderWidget: (model: ReactWidget) => React.ReactNode;
}

export class ReactWidget extends SceneObjectBase<ReactWidgetState> {
  constructor(state: ReactWidgetState) {
    super(state);
  }

  static Component = ({ model }: SceneComponentProps<ReactWidget>) => {
    const { renderWidget, title, isContentEditing, type } = model.useState();
    const { isEditing, deleteWidget } = useContext(LayoutEditContext);
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

    const toggleContentEdit = (e: React.MouseEvent) => {
      e.stopPropagation();
      model.setState({ isContentEditing: !isContentEditing });
    };

    const handleDelete = (e: React.MouseEvent) => {
      e.stopPropagation();
      if (model.state.key) {
        deleteWidget(model.state.key);
      }
    };

    const isEditableType = type === 'markdown';

    return (
      <div className="scene-react-widget" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
        {(title || (isEditing && titleEditing) || isEditing) && (
          <div 
            className="panel-header grid-drag-handle-dashboard-grid"
            onClick={handleTitleClick}
            style={{ 
              cursor: isEditing ? 'pointer' : 'default', 
              border: isEditing ? '1px dashed var(--text-secondary)' : 'none',
              position: 'relative'
            }}
            title={isEditing ? "Click to edit title" : ""}
          >
            {titleEditing ? (
               <input
                 className="panel-header-input"
                 value={tempTitle}
                 onChange={handleTitleChange}
                 onBlur={handleTitleBlur}
                 onKeyDown={handleKeyDown}
                 autoFocus
                 style={{
                   flex: 1,
                   background: 'var(--bg-input)',
                   border: 'none',
                   color: 'var(--text-primary)',
                   padding: '2px 4px',
                   fontSize: '14px',
                   height: '24px'
                 }}
               />
            ) : (
              <span className="panel-title-text">{title}</span>
            )}

            {isEditing && (
              <div className="widget-header-controls" style={{ position: 'relative', top: '0', right: '0' }} onClick={e => e.stopPropagation()}>
                {isEditableType && (
                   <button
                     className="widget-control-btn widget-edit-btn"
                     onClick={toggleContentEdit}
                   >
                     {isContentEditing ? '보기' : '편집'}
                   </button>
                )}
                {type === 'markdown' && (
                  <button
                    className="widget-control-btn widget-delete-btn"
                    onClick={handleDelete}
                    title="위젯 삭제"
                  >
                    ✕
                  </button>
                )}
              </div>
            )}
          </div>
        )}
        <div className="panel-content" style={{ flex: 1, position: 'relative', overflow: 'visible' }}>
          {renderWidget(model)}
        </div>
      </div>
    );
  };
}
