import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Monitor, Tv, Layers, Home } from 'lucide-react';
import './Navigation.css';

const Navigation = () => {
  const location = useLocation();
  
  const navItems = [
    { path: '/', label: 'Dashboard', icon: Home },
    { path: '/scenes', label: 'Scenes', icon: Layers },
    { path: '/channels', label: 'Channels', icon: Tv },
    { path: '/display', label: 'Display', icon: Monitor },
  ];

  return (
    <nav className="navigation">
      <div className="navigation-header">
        <h1 className="navigation-title">Mimir</h1>
        <p className="navigation-subtitle">Platform Control</p>
      </div>
      
      <ul className="navigation-menu">
        {navItems.map(({ path, label, icon: Icon }) => (
          <li key={path}>
            <NavLink
              to={path}
              className={({ isActive }) =>
                `navigation-link ${isActive ? 'navigation-link-active' : ''}`
              }
              end={path === '/'}
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
      
      {/* Debug info - remove this after testing */}
      <div style={{ fontSize: '10px', color: '#666', padding: '10px' }}>
        Current: {location.pathname}
      </div>
    </nav>
  );
};

export default Navigation;
