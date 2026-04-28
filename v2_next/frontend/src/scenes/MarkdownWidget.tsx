import React, { useContext, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { LayoutEditContext } from '../domains/Configuration/context/LayoutEditContext';
import { LABELS } from '../shared/constants/uiText';
import type { DashboardItem } from './DashboardScene';
import type { ReactWidget } from './ReactWidgetObject';

interface MarkdownWidgetProps {
  item: DashboardItem;
  model: ReactWidget;
}

export const MarkdownWidget = ({ item, model }: MarkdownWidgetProps): JSX.Element => {
  const { updateWidget } = useContext(LayoutEditContext);
  const { isContentEditing: editing, properties } = model.useState();
  const currentProperties = properties ?? item.properties ?? {};
  const currentContent =
    typeof currentProperties.content === 'string' ? currentProperties.content : '';
  const [editValue, setEditValue] = useState(currentContent);

  useEffect(() => {
    setEditValue(currentContent);
  }, [currentContent]);

  const handleSave = (): void => {
    const nextProperties = {
      ...currentProperties,
      content: editValue,
    };
    updateWidget(item.key, { properties: nextProperties });
    model.setState({ properties: nextProperties, isContentEditing: false });
  };

  return (
    <div className="scene-react-widget card" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {editing ? (
        <div className="notice-editor-container">
          <textarea
            className="notice-textarea"
            value={editValue}
            onChange={(event) => setEditValue(event.target.value)}
          />
          <button className="notice-save-btn" onClick={handleSave}>{LABELS.SAVE}</button>
        </div>
      ) : (
        <div className="notice-content markdown-body" style={{ flex: 1, overflow: 'auto' }}>
          <ReactMarkdown>{currentContent}</ReactMarkdown>
        </div>
      )}
    </div>
  );
};
