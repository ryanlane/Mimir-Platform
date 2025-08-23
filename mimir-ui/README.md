# Mimir Platform Web Interface

A modern, minimal React frontend for the Mimir Platform API, inspired by Dieter Rams' design principles.

## Features

- **Dashboard**: Overview of system status, active scenes, and channels
- **Scenes Management**: Create, edit, and control display scenes
- **Channels Configuration**: Manage channel settings and test image generation
- **Display Control**: Monitor hardware status and control the e-ink display
- **Minimal Design**: Clean, functional interface following Dieter Rams' design language

## Quick Start

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start development server:
   ```bash
   npm start
   ```

3. Build for production:
   ```bash
   npm build
   ```

## API Configuration

The application connects to the Mimir Platform API at:
- **Development**: `http://172.31.79.107:5000/api`
- **Documentation**: `http://172.31.79.107:5000/docs`

## 📖 Documentation

**Complete documentation is available at:** [github.com/ryanlane/mimir-documentation](https://github.com/ryanlane/mimir-documentation)

- **[Frontend Integration Guide](https://github.com/ryanlane/mimir-documentation/blob/main/FRONTEND_INTEGRATION_GUIDE.md)** - Frontend development patterns
- **[Frontend API Reference](https://github.com/ryanlane/mimir-documentation/blob/main/FRONTEND_API_REFERENCE.md)** - JavaScript integration examples
- **[API Documentation](https://github.com/ryanlane/mimir-documentation/blob/main/API_DOCUMENTATION.md)** - Complete REST API reference
- **[Channel Architecture](https://github.com/ryanlane/mimir-documentation/blob/main/CHANNEL_ARCHITECTURE.md)** - Channel Web Components guide

## Design Principles

This interface follows Dieter Rams' ten principles of good design, focusing on minimal, functional design with purposeful typography and clean interactions.

## Technology Stack

- **React 19**: Modern React with hooks and functional components
- **React Router**: Client-side routing
- **Axios**: HTTP client for API communication
- **Lucide React**: Minimal, consistent icons
- **CSS Custom Properties**: Design system with consistent spacing and colors

```
src/
├── components/
│   ├── Layout/           # Main layout and navigation
│   └── Button/           # Reusable button component
├── pages/
│   ├── Dashboard/        # System overview dashboard
│   ├── Scenes/           # Scene management
│   ├── Channels/         # Channel configuration
│   └── Display/          # Display control
├── services/
│   └── api.js           # API client and service methods
├── App.js               # Main application component
├── App.css              # Global component styles
└── index.css            # Design system and utilities
```

## Design System

The interface uses a consistent design system with:

- **Colors**: Monochromatic palette with selective use of accent colors
- **Typography**: System fonts with careful hierarchy
- **Spacing**: 8px base unit with consistent scale
- **Components**: Minimal, functional design patterns
- **Layout**: Clean grid systems and thoughtful white space

## Color Palette

- **Primary**: `#000000` (Black)
- **Secondary**: `#333333` (Dark Gray)
- **Tertiary**: `#666666` (Medium Gray)
- **Background**: `#ffffff` (White)
- **Surface**: `#f8f8f8` (Light Gray)
- **Accent**: `#0066cc` (Blue)

## Usage

1. Start the development server: `npm start`
2. Navigate to the running application (typically `http://localhost:3000`)
3. Use the sidebar navigation to access different sections:
   - **Dashboard**: View system overview and quick actions
   - **Scenes**: Create and manage display scenes
   - **Channels**: Configure content channels
   - **Display**: Control the hardware display

## API Integration

The application integrates with the Mimir Platform API providing:

- **Real-time status**: Live updates of display and channel status
- **Scene management**: Full CRUD operations for scenes
- **Channel configuration**: Dynamic settings based on channel schemas
- **Display control**: Hardware monitoring and control

## Development

The application follows modern React best practices:

- Functional components with hooks
- Consistent error handling and loading states
- Responsive design for mobile and desktop
- Accessible markup and keyboard navigation
- Clean separation of concerns

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)
