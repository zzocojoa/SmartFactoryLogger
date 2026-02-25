import React from 'react';
import type { PageSidebarViewProps } from '../types/PageSidebar.types';
import {
  createCategoryContentStyle,
  createCategoryHeaderStyle,
  createPageButtonStyle,
  createSidebarRootStyle,
  createSidebarSectionStyle,
  sidebarCategoryItemStyle,
  sidebarChevronStyle,
  sidebarEmptyTextStyle,
  sidebarErrorTextStyle,
  sidebarHeaderTitleStyle,
  sidebarListItemStyle,
  sidebarListStyle,
  sidebarLoadingTextStyle,
  sidebarPageBulletStyle,
} from '../utils/PageSidebar.utils';

export const PageSidebarView: React.FC<PageSidebarViewProps> = ({
  selectedPage,
  onSelectPage,
  pageItems,
  loading = false,
  error = null,
  isOpen,
  model,
}) => {
  const { groupedPages, categoryKeys, expandedCategories, toggleCategory } = model;

  return (
    <div style={createSidebarRootStyle(isOpen)}>
      <div
        style={createSidebarSectionStyle(isOpen, {
          padding: '1.5rem',
          borderBottom: '1px solid var(--border-color)',
        })}
      >
        <h3 style={sidebarHeaderTitleStyle}>MES Reports</h3>
      </div>

      <div
        style={createSidebarSectionStyle(isOpen, {
          flex: 1,
          overflowY: 'auto',
          padding: '1rem',
        })}
      >
        {loading && <div style={sidebarLoadingTextStyle}>Loading...</div>}
        {error && <div style={sidebarErrorTextStyle}>{error}</div>}

        {!loading && pageItems.length === 0 && <div style={sidebarEmptyTextStyle}>No pages found.</div>}

        {categoryKeys.map((category) => {
          const isExpanded = expandedCategories.has(category);
          const categoryPages = groupedPages[category] ?? [];

          return (
            <div key={category} style={sidebarCategoryItemStyle}>
              <div
                onClick={() => toggleCategory(category)}
                style={createCategoryHeaderStyle()}
                onMouseEnter={(event) => {
                  event.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                }}
                onMouseLeave={(event) => {
                  event.currentTarget.style.background = 'transparent';
                }}
              >
                <span>{category}</span>
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={sidebarChevronStyle(isExpanded)}
                >
                  <path d="M6 9l6 6 6-6" />
                </svg>
              </div>

              <div style={createCategoryContentStyle(isExpanded)}>
                <ul style={sidebarListStyle}>
                  {categoryPages.map((item) => {
                    const isSelected = selectedPage === item.key;

                    return (
                      <li key={item.key} style={sidebarListItemStyle}>
                        <button onClick={() => onSelectPage(item.key)} style={createPageButtonStyle(isSelected)}>
                          <span style={sidebarPageBulletStyle}>•</span>
                          {item.name}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </div>
          );
        })}
      </div>

      <div
        style={createSidebarSectionStyle(isOpen, {
          padding: '1rem',
          borderTop: '1px solid var(--border-color)',
          fontSize: '0.8rem',
          color: 'var(--text-secondary)',
        })}
      >
        Smart Factory MES
      </div>
    </div>
  );
};
