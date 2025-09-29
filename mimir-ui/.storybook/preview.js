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
  document.documentElement.setAttribute('data-theme', context.globals.theme);
  return <Story />;
};

export const decorators = [withTheme];

// Optionally set an initial global viewport (Storybook 8 may also use globals)
export const initialGlobals = {
  viewport: { value: 'desktop', isRotated: false }
};
