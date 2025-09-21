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
