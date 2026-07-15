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

import React from 'react';
import PropTypes from 'prop-types';
import { ArrowDownUp } from 'lucide-react';
import './SortToolbar.css';

/**
 * SortToolbar — direction toggle + sort field select.
 * Pairs with the useSortPreference hook for persisted state.
 */
const SortToolbar = ({ sortBy, sortDir, options, onChangeSortBy, onToggleSortDir, selectAriaLabel }) => (
  <div className="sort-toolbar">
    <button
      type="button"
      className="sort-direction-toggle"
      onClick={onToggleSortDir}
      aria-label={sortDir === 'asc' ? 'Sort ascending' : 'Sort descending'}
      title={sortDir === 'asc' ? 'Ascending' : 'Descending'}
    >
      <ArrowDownUp size={16} className={sortDir === 'desc' ? 'sort-direction-toggle--desc' : ''} />
    </button>
    <select
      value={sortBy}
      onChange={(e) => onChangeSortBy(e.target.value)}
      aria-label={selectAriaLabel}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>Sort: {opt.label}</option>
      ))}
    </select>
  </div>
);

SortToolbar.propTypes = {
  sortBy: PropTypes.string.isRequired,
  sortDir: PropTypes.oneOf(['asc', 'desc']).isRequired,
  options: PropTypes.arrayOf(PropTypes.shape({
    value: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
  })).isRequired,
  onChangeSortBy: PropTypes.func.isRequired,
  onToggleSortDir: PropTypes.func.isRequired,
  selectAriaLabel: PropTypes.string,
};

SortToolbar.defaultProps = {
  selectAriaLabel: 'Sort by',
};

export default SortToolbar;
