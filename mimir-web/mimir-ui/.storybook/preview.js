// .storybook/preview.ts (or .js)
/** @type { import('@storybook/react-webpack5').Preview } */
import { MINIMAL_VIEWPORTS, INITIAL_VIEWPORTS } from 'storybook/viewport';

import '../src/styles/theme.css';

// Your custom viewport presets
const CUSTOM_VIEWPORTS = {
  responsive: {
    name: 'Responsive (fluid)',
    styles: { width: '100%', height: '100%' },
    type: 'desktop',
  },
  desktop: {
    name: 'Desktop 1440',
    styles: { width: '1440px', height: '900px' },
    type: 'desktop',
  },
  tablet: {
    name: 'Tablet 834', // iPad Air logical width (portrait)
    styles: { width: '834px', height: '1112px' },
    type: 'tablet',
  },
  mobile: {
    name: 'Mobile 390', // Modern iPhone logical width
    styles: { width: '390px', height: '844px' },
    type: 'mobile',
  },
};

// Theme toolbar
const globalTypes = {
  theme: {
    name: 'Theme',
    description: 'Global theme for components',
    defaultValue: 'light',
    toolbar: {
      icon: 'mirror',
      items: [
        { value: 'light', title: 'Light' },
        { value: 'dark', title: 'Dark' },
      ],
      showName: true,
    },
  },
};

// Theme decorator
const withTheme = (Story, context) => {
  const theme = context.globals.theme;
  document.documentElement.setAttribute('data-theme', theme);

  const lightBg = 'var(--color-app-background, #ffffff)';
  const darkBg = 'var(--color-app-background, #0e1116)';
  const background = theme === 'dark' ? darkBg : lightBg;

  document.body.style.background = background;
  document.body.style.color =
    theme === 'dark' ? 'var(--color-text, #f5f7fa)' : 'var(--color-text, #1a1d21)';

  return (
    <div style={{ background, transition: 'background .25s ease' }}>
      <Story />
    </div>
  );
};

const preview = {
  // Use the single object export style Storybook recommends
  parameters: {
    controls: {
      matchers: { color: /(background|color)$/i, date: /Date$/i },
    },
    viewport: {
      // Per docs: use `options` (not `viewports`)
      // Choose which base set you want:
      //   - MINIMAL_VIEWPORTS: mobile1, mobile2, tablet
      //   - INITIAL_VIEWPORTS: detailed device list
      // Here we take MINIMAL as a base and add your customs.
      options: {
        ...MINIMAL_VIEWPORTS,
        ...CUSTOM_VIEWPORTS,
      },
      // NOTE: `defaultViewport` is deprecated in favor of initialGlobals/globals.
    },
    // Backgrounds: define named swatches for the toolbar
    // Keys (e.g. 'light', 'dark') become the values you set in globals/backgrounds.
    backgrounds: {
      options: {
        light: { name: 'Light', value: '#ffffff' },
        dark:  { name: 'Dark',  value: '#0e1116' },
        // Optional extras while designing:
        // gray:  { name: 'Gray',  value: '#f5f5f7' },
        // ink:   { name: 'Ink',   value: '#111318' },
      },
      // grid can be toggled globally or per-story via globals.backgrounds.grid
      // grid: true,
    },
  },

  // Set the initial viewport selection the new way
  initialGlobals: {
    viewport: { value: 'desktop', isRotated: false }, // must match one of the keys in `options`
  },

  // Keep your theme toolbar + decorator
  globalTypes,
  decorators: [withTheme],
};

export default preview;
