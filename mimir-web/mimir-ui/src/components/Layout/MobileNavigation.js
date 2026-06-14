import React from 'react';
import { NavLink } from 'react-router-dom';
import { Settings, Layers, Monitor, Database } from 'lucide-react';
import './MobileNavigation.css';

const MobileNavigation = () => {
  const navItems = [
    { path: '/screens', label: 'Screens', icon: Monitor },
    { path: '/programs', label: 'Programs', icon: Layers },
    { path: '/sources', label: 'Sources', icon: Database },
    { path: '/settings', label: 'System', icon: Settings },
  ];

  return (
    <nav className="mobile-navigation">
      <div className="mobile-nav-items">
        {navItems.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              `mobile-nav-item ${isActive ? 'mobile-nav-item-active' : ''}`
            }

          >
            <div className="mobile-nav-icon">
              <Icon size={20} strokeWidth={1.5} />
            </div>
            <span className="mobile-nav-label">{label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
};

export default MobileNavigation;
