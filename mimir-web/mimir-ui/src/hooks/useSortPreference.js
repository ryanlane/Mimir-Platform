// Copyright (C) 2026 Ryan Lane
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published
// by the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

import { useState } from 'react';

/**
 * Sort field + direction state persisted to localStorage.
 *
 * @param {string} storagePrefix - e.g. 'mimir.sources' → keys 'mimir.sources.sortBy' / '.sortDir'
 * @param {string} defaultSortBy
 * @returns {{ sortBy: string, setSortBy: Function, sortDir: 'asc'|'desc', toggleSortDir: Function }}
 */
export function useSortPreference(storagePrefix, defaultSortBy = 'name') {
  const [sortBy, setSortByState] = useState(() => {
    try { return localStorage.getItem(`${storagePrefix}.sortBy`) || defaultSortBy; } catch { return defaultSortBy; }
  });
  const [sortDir, setSortDirState] = useState(() => {
    try { return localStorage.getItem(`${storagePrefix}.sortDir`) || 'asc'; } catch { return 'asc'; }
  });

  const setSortBy = (value) => {
    setSortByState(value);
    try { localStorage.setItem(`${storagePrefix}.sortBy`, value); } catch { /* private mode */ }
  };

  const toggleSortDir = () => {
    const next = sortDir === 'asc' ? 'desc' : 'asc';
    setSortDirState(next);
    try { localStorage.setItem(`${storagePrefix}.sortDir`, next); } catch { /* private mode */ }
  };

  return { sortBy, setSortBy, sortDir, toggleSortDir };
}

export default useSortPreference;
