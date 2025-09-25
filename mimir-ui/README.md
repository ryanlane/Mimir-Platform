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

## Build & Version Automation

This project generates a build version automatically every time you run `npm run build` (or any script that invokes the build step). The script `scripts/gen-version.mjs` creates/updates two artifacts:

- `src/version.js` – Exports `APP_VERSION` and attaches it to `window.__APP_VERSION__`.
- `public/version.json` – Runtime-readable manifest used by the PWA update hook.

### Version Format
`YYYY.MM.DD-HHMMSS[-<gitsha>][-<CHANNEL>][+meta]`

Examples:
- `2025.09.25-142355-1a2b3c` (UTC timestamp + git short SHA)
- `2025.09.25-142355-1a2b3c-RC` (release candidate channel)
- `2025.09.25-142355+hotfix42` (with metadata)

Lexical ordering matches chronological ordering because of fixed-width date/time components.

### Environment Variables
You can influence generation with:

| Variable | Purpose |
|----------|---------|
| `APP_VERSION` | Set explicit version (bypass auto) |
| `BUILD_ID` / `BUILD_NUMBER` | Populates `build` field in `version.json` |
| `BUILD_META` | Appended after `+` (e.g. `+hotfix`) |
| `VERSION_CHANNEL` | Adds suffix after build (e.g. `-RC`, `-PROD`, `-DEV`) |
| `CRITICAL_UPDATE=true` | Marks manifest `critical: true` (UI can force reload) |
| `MIN_CLIENT=version` | Sets minimum client version required to continue |
| `FORCE_VERSION_DOWNGRADE=true` | Allow writing an older version (normally blocked) |

### Critical vs Min Client
- `critical: true` – Signals clients an update is strongly recommended; UX shows an upgrade toast/dialog.
- `minClient` – If a client’s current `APP_VERSION` < `minClient`, the app can block interaction until updated (optional UI enforcement to be implemented).

### Manual Invocation
Run it directly if needed:
```bash
node scripts/gen-version.mjs
```

### Workflow Integration
1. Developer runs `npm run build` – prebuild hook auto-generates version.
2. Service worker & `usePwaUpdates` hook fetch `/version.json` periodically.
3. If a new version is found, user receives an update toast; critical/minClient logic adjusts messaging.

### Safe Editing
If you manually change `src/version.js` it will be overwritten on next build. Only commit manual edits for emergency patches if you do NOT run a build locally afterwards.

---
