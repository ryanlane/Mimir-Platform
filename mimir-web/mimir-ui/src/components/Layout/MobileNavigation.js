import React from 'react';
import { NavLink } from 'react-router-dom';
import { Settings, Tv, Layers, Home, MonitorSpeaker, Database } from 'lucide-react';
import './MobileNavigation.css';

const MobileNavigation = () => {
  const navItems = [
    { path: '/', label: 'Dashboard', icon: Home },
    { path: '/scenes', label: 'Scenes', icon: Layers },
    { path: '/channels', label: 'Channels', icon: Tv },
    { path: '/displays', label: 'Displays', icon: MonitorSpeaker },
    // { path: '/distribution', label: 'Distribution', icon: Database },
    { path: '/settings', label: 'Settings', icon: Settings },
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
            end={path === '/'}
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
