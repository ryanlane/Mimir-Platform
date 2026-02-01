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
