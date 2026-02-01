import React from 'react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import MobileNavigation from './MobileNavigation';

export default {
  title: 'Layout/MobileNavigation',
  component: MobileNavigation,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'iOS-style bottom tab navigation. Only visible under 768px width via CSS media queries. Resize the Storybook preview (or use the viewport addon) to below 768px to see it.'
      }
    }
  }
};

function Wrapper({ initialEntries = ['/'] }) {
  return (
    <MemoryRouter initialEntries={initialEntries}>
      <div style={{ minHeight: '340px', paddingBottom: '80px', position: 'relative', border: '1px solid var(--color-border)' }}>
        <Routes>
          <Route path="/" element={<div style={{ padding: '1rem' }}>Dashboard Content</div>} />
          <Route path="/scenes" element={<div style={{ padding: '1rem' }}>Scenes Content</div>} />
          <Route path="/channels" element={<div style={{ padding: '1rem' }}>Channels Content</div>} />
          <Route path="/displays" element={<div style={{ padding: '1rem' }}>Displays Content</div>} />
          <Route path="/settings" element={<div style={{ padding: '1rem' }}>Settings Content</div>} />
        </Routes>
        <MobileNavigation />
      </div>
    </MemoryRouter>
  );
}

export const DashboardActive = {
  render: () => <Wrapper initialEntries={['/']} />
};
export const ScenesActive = { render: () => <Wrapper initialEntries={['/scenes']} /> };
export const ChannelsActive = { render: () => <Wrapper initialEntries={['/channels']} /> };
export const DisplaysActive = { render: () => <Wrapper initialEntries={['/displays']} /> };
export const SettingsActive = { render: () => <Wrapper initialEntries={['/settings']} /> };
