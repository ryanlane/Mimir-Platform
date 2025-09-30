/** @type { import('@storybook/react-webpack5').Preview } */

import '../src/styles/theme.css';

// Custom viewport presets (desktop, tablet, mobile)
const CUSTOM_VIEWPORTS = {
  desktop: {
    name: 'Desktop 1440',
    styles: { width: '1440px', height: '900px' },
    type: 'desktop'
  },
  tablet: {
    name: 'Tablet 834', // iPad Air logical width portrait
    styles: { width: '834px', height: '1112px' },
    type: 'tablet'
  },
  mobile: {
    name: 'Mobile 390', // Modern iPhone logical width
    styles: { width: '390px', height: '844px' },
    type: 'mobile'
  }
};

export const parameters = {
  controls: {
    matchers: { color: /(background|color)$/i, date: /Date$/i },
  },
  viewport: {
    viewports: CUSTOM_VIEWPORTS,
    defaultViewport: 'desktop'
  }
};

export const globalTypes = {
  theme: {
    name: 'Theme',
    description: 'Global theme for components',
    defaultValue: 'light',
    toolbar: {
      icon: 'mirror',
      items: [
        { value: 'light', title: 'Light' },
        { value: 'dark',  title: 'Dark'  },
      ],
      showName: true,
    },
  },
};

const withTheme = (Story, context) => {
  const theme = context.globals.theme;
  document.documentElement.setAttribute('data-theme', theme);

  // Derive a sensible background for the canvas area. Prefer CSS vars if available.
  // Fallback colors chosen for good contrast.
  const lightBg = 'var(--color-app-background, #ffffff)';
  const darkBg = 'var(--color-app-background, #0e1116)';
  const background = theme === 'dark' ? darkBg : lightBg;

  // Apply to body so full-height stories (modals, layouts) inherit it.
  document.body.style.background = background;
  document.body.style.color = theme === 'dark' ? 'var(--color-text, #f5f7fa)' : 'var(--color-text, #1a1d21)';

  // Wrap story to ensure consistent min-height and smooth transition.
  return (
    <div style={{      
      background,
      transition: 'background .25s ease'
    }}>
      <Story />
    </div>
  );
};

export const decorators = [withTheme];

// Optionally set an initial global viewport (Storybook 8 may also use globals)
export const initialGlobals = {
  viewport: { value: 'desktop', isRotated: false }
};
