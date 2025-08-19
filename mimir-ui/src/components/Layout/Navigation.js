import React from 'react';
import { NavLink } from 'react-router-dom';
import { Monitor, Settings, Layers, Home } from 'lucide-react';
import './Navigation.css';

const Navigation = () => {
  const navItems = [
    { path: '/', label: 'Dashboard', icon: Home },
    { path: '/scenes', label: 'Scenes', icon: Layers },
    { path: '/channels', label: 'Channels', icon: Settings },
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
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
};

export default Navigation;
