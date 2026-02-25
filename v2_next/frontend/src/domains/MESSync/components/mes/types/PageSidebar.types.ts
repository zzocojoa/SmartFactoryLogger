export interface PageItem {
  key: string;
  name: string;
  category: string;
}

export interface PageSidebarProps {
  selectedPage: string | null;
  onSelectPage: (page: string) => void;
  pageItems: PageItem[];
  loading?: boolean;
  error?: string | null;
  isOpen: boolean;
}

export interface PageSidebarModel {
  groupedPages: Record<string, PageItem[]>;
  categoryKeys: string[];
  expandedCategories: Set<string>;
  toggleCategory: (category: string) => void;
}

export interface PageSidebarViewProps extends PageSidebarProps {
  model: PageSidebarModel;
}
