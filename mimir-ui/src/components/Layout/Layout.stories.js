import React from 'react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Layout from './Layout';

export default {
  title: 'Layout/AppLayout',
  component: Layout,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'Full application shell combining desktop sidebar navigation, main content area, and mobile bottom navigation. Resize below 768px to see mobile nav.'
      }
    }
  }
};

const DemoPage = ({ title }) => (
  <div style={{ maxWidth: 900 }}>
    <h2 style={{ marginTop: 0 }}>{title}</h2>
    <p>This is example content for the {title} page. Replace with real routed content in the application.</p>
  </div>
);

const LongContent = () => (
  <div style={{ maxWidth: 900 }}>
    <h2>Lots of Content</h2>
    {[...Array(40)].map((_, i) => (
      <p key={i}>Paragraph {i + 1}: Lorem ipsum dolor sit amet, consectetur adipiscing elit. Curabitur at sem a sapien efficitur viverra.</p>
    ))}
  </div>
);

function AppWrapper({ initialEntries = ['/'] }) {
  return (
    <MemoryRouter initialEntries={initialEntries}>
      <Layout>
        <Routes>
          <Route path="/" element={<DemoPage title="Dashboard" />} />
          <Route path="/scenes" element={<DemoPage title="Scenes" />} />
          <Route path="/channels" element={<DemoPage title="Channels" />} />
          <Route path="/displays" element={<DemoPage title="Displays" />} />
          <Route path="/settings" element={<DemoPage title="Settings" />} />
          <Route path="/long" element={<LongContent />} />
        </Routes>
      </Layout>
    </MemoryRouter>
  );
}

export const Basic = {
  render: () => <AppWrapper initialEntries={['/']} />,
  parameters: { docs: { description: { story: 'Dashboard route in full layout.' } } }
};

export const Scenes = { render: () => <AppWrapper initialEntries={['/scenes']} /> };
export const Channels = { render: () => <AppWrapper initialEntries={['/channels']} /> };
export const WithLongScroll = { render: () => <AppWrapper initialEntries={['/long']} /> };

export const MobileView = {
  render: () => <AppWrapper initialEntries={['/settings']} />,
  parameters: {
    docs: { description: { story: 'Use Storybook viewport addon to switch to a mobile width (<768px) to view bottom navigation.' } }
  }
};
