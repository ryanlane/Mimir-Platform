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
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Navigation from './Navigation';

export default {
  title: 'Layout/Navigation',
  component: Navigation,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'Primary desktop sidebar navigation. Uses react-router NavLink for active state styling.'
      }
    }
  }
};

function Wrapper({ initialEntries = ['/'] }) {
  return (
    <MemoryRouter initialEntries={initialEntries}>
      <div style={{ display: 'flex', minHeight: '400px', border: '1px solid var(--color-border)' }}>
        <Navigation />
        <div style={{ padding: '1rem', flex: 1 }}>
          <Routes>
            <Route path="/" element={<div>Dashboard Content</div>} />
            <Route path="/scenes" element={<div>Scenes Content</div>} />
            <Route path="/channels" element={<div>Channels Content</div>} />
            <Route path="/displays" element={<div>Displays Content</div>} />
            <Route path="/settings" element={<div>Settings Content</div>} />
          </Routes>
        </div>
      </div>
    </MemoryRouter>
  );
}

export const DashboardActive = {
  render: () => <Wrapper initialEntries={['/']} />,
  parameters: { docs: { description: { story: 'Dashboard route active.' } } }
};

export const ScenesActive = {
  render: () => <Wrapper initialEntries={['/scenes']} />
};

export const ChannelsActive = {
  render: () => <Wrapper initialEntries={['/channels']} />
};

export const DisplaysActive = {
  render: () => <Wrapper initialEntries={['/displays']} />
};

export const SettingsActive = {
  render: () => <Wrapper initialEntries={['/settings']} />
};
