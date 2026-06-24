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

/**
 * ValidationErrors
 * Simple presentational component to render a list of validation error messages.
 * Accepts an array of strings. Returns null if empty/undefined.
 */
const ValidationErrors = ({ errors }) => {
  if (!errors || errors.length === 0) return null;
  return (
    <div className="validation-errors">
      <h4>Validation Errors:</h4>
      <ul>
        {errors.map((error, idx) => (
          <li key={idx}>{error}</li>
        ))}
      </ul>
    </div>
  );
};

export default ValidationErrors;

ValidationErrors.propTypes = {
  errors: PropTypes.arrayOf(PropTypes.string)
};
