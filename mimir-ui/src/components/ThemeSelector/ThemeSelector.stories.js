import React, { useState, useMemo } from 'react';
import ThemeSelector from './ThemeSelector';
import { ThemeContext } from '../../App';

export default {
  title: 'Components/ThemeSelector',
  component: ThemeSelector,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'Theme mode picker (System / Light / Dark). Uses a ThemeContext value shaped like the return of useSystemTheme(). The stories provide a lightweight mock so selection is interactive.'
      }
    }
  }
};

// Simple mock of the real hook state shape
function ThemeProviderMock({ initialPreference = 'system', children }) {
  const [preference, setPreference] = useState(initialPreference);
  const resolvedTheme = preference === 'system' ? 'light' : preference; // naive resolution
  const value = useMemo(() => ({
    preference,
    resolvedTheme,
    setThemePreference: setPreference
  }), [preference, resolvedTheme]);
  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

const Template = (args) => (
  <ThemeProviderMock initialPreference={args.initialPreference}>
    <div style={{ maxWidth: 340 }}>
      <ThemeSelector />
    </div>
  </ThemeProviderMock>
);

export const System = {
  render: Template,
  args: { initialPreference: 'system' },
  parameters: {
    docs: { description: { story: 'System preference (mock resolves to light here).' } }
  }
};

export const LightSelected = {
  render: Template,
  args: { initialPreference: 'light' },
  parameters: {
    docs: { description: { story: 'Light preference active.' } }
  }
};

export const DarkSelected = {
  render: Template,
  args: { initialPreference: 'dark' },
  parameters: {
    docs: { description: { story: 'Dark preference active.' } }
  }
};

export const InteractiveSwitching = {
  render: () => (
    <ThemeProviderMock initialPreference="system">
      <div style={{ maxWidth: 340 }}>
        <ThemeSelector />
        <p style={{ fontSize: '0.7rem', opacity: 0.7, marginTop: '0.75rem' }}>Use the buttons above to switch. System resolves to light in this mock.</p>
      </div>
    </ThemeProviderMock>
  ),
  parameters: {
    docs: { description: { story: 'Fully interactive example with mock provider state.' } }
  }
};
