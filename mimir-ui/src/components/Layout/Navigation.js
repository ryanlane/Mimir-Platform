import React from 'react';
import { NavLink } from 'react-router-dom';
import { Settings, Tv, Layers, Home, MonitorSpeaker, Database } from 'lucide-react';
import './Navigation.css';
import Logo from '../../components/Brand/Logo';

const Navigation = () => {
  const navItems = [
    { path: '/', label: 'Dashboard', icon: Home },
    { path: '/scenes', label: 'Scenes', icon: Layers },
    { path: '/channels', label: 'Channels', icon: Tv },
    { path: '/displays', label: 'Displays', icon: MonitorSpeaker },
    // { path: '/distribution', label: 'Distribution', icon: Database },
    { path: '/settings', label: 'Settings', icon: Settings },
  ];

  return (
    <nav className="navigation">
      <div className="navigation-header">
        <div className="navigation-brand" style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <Logo size={38} />
          <div className="navigation-brand-text" style={{ display: 'flex', flexDirection: 'column' }}>
            <h1 className="navigation-title" style={{ margin: 0 }}>Mimir</h1>
          </div>
        </div>
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
      
      
    </nav>
  );
};

export default Navigation;
