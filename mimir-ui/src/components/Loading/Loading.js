import React from 'react';
import './Loading.css';

const Loading = ({ message = 'Loading...' }) => {
  return (
    <div className="loading">
      <div className="loading-spinner"></div>
      <span className="loading-message">{message}</span>
    </div>
  );
};

export default Loading;
