export type ProjectSortBy = 'name' | 'created_at' | 'manual';
export type ProjectSortOrder = 'asc' | 'desc';

export type ProjectSortState = {
  sortBy: ProjectSortBy;
  sortOrder: ProjectSortOrder;
};

export const PROJECT_SORT_STORAGE_KEY = 'ibra_projects_sort';

export function readProjectSortFromStorage(): ProjectSortState {
  try {
    const raw = localStorage.getItem(PROJECT_SORT_STORAGE_KEY);
    if (!raw) return { sortBy: 'created_at', sortOrder: 'desc' };
    const parsed = JSON.parse(raw) as ProjectSortState;
    if (
      (parsed.sortBy === 'name' ||
        parsed.sortBy === 'created_at' ||
        parsed.sortBy === 'manual') &&
      (parsed.sortOrder === 'asc' || parsed.sortOrder === 'desc')
    ) {
      return parsed;
    }
  } catch {
    /* ignore */
  }
  return { sortBy: 'created_at', sortOrder: 'desc' };
}

export function writeProjectSortToStorage(sort: ProjectSortState) {
  localStorage.setItem(PROJECT_SORT_STORAGE_KEY, JSON.stringify(sort));
}
