import React from 'react';
import Navigation from './Navigation';
import './Layout.css';

const Layout = ({ children }) => {
  return (
    <div className="layout">
      <Navigation />
      <main className="layout-main">
        {children}
      </main>
    </div>
  );
};

export default Layout;
