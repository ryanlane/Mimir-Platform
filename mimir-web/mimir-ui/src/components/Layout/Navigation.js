// Copyright (C) 2026 Ryan Lane
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published
// by the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

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
