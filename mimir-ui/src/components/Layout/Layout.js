import React from 'react';
import Navigation from './Navigation';
import MobileNavigation from './MobileNavigation';
import './Layout.css';

const Layout = ({ children }) => {
  return (
    <div className="layout">
      <Navigation />
      <main className="layout-main">
        {children}
      </main>
      <MobileNavigation />
    </div>
  );
};

export default Layout;
