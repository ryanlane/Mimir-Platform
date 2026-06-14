import React from 'react';
import { NavLink } from 'react-router-dom';
import { Settings, Layers, Monitor, Database } from 'lucide-react';
import './Navigation.css';
import Logo from '../../components/Brand/Logo';

const primaryNav = [
  { path: '/screens', label: 'Screens', icon: Monitor },
  { path: '/programs', label: 'Programs', icon: Layers },
  { path: '/sources', label: 'Sources', icon: Database },
];

const Navigation = () => {
  return (
    <nav className="navigation">
      <div className="navigation-header">
        <div className="navigation-brand">
          <Logo size={32} />
          <h1 className="navigation-title">mimir</h1>
        </div>
      </div>

      <ul className="navigation-menu">
        {primaryNav.map(({ path, label, icon: Icon }) => (
          <li key={path}>
            <NavLink
              to={path}
              className={({ isActive }) =>
                `navigation-link ${isActive ? 'navigation-link-active' : ''}`
              }
            >
              <Icon size={16} />
              <span>{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>

      <div className="navigation-footer">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `navigation-link navigation-link-system ${isActive ? 'navigation-link-active' : ''}`
          }
        >
          <Settings size={16} />
          <span>System</span>
        </NavLink>
      </div>
    </nav>
  );
};

export default Navigation;
