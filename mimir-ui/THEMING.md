# Mimir UI Theming

The UI now supports automatic dark mode using CSS custom properties and `prefers-color-scheme`, plus an in-app selector for Light / Dark / System.

## How it works
- `src/theme.css` defines base (light) variables and dark overrides inside `@media (prefers-color-scheme: dark)`.
- The hook `useSystemTheme` manages a user preference (`light`, `dark`, or `system`) stored in `localStorage` under `mimir-theme-preference`.
- The effective theme is reflected on `document.documentElement.dataset.theme` as either `light` or `dark` (resolved value) to allow future class-based overrides.
- The `<meta name="color-scheme" content="light dark" />` hint enables UA components (form controls, scrollbars in supporting browsers) to adapt.

## Adding new semantic tokens
If a component needs a new color, add a variable to `:root` in `theme.css` and provide a dark override. Avoid hard-coded hex values inside component styles; always use a semantic variable.

Example:
```css
:root { --color-info: #3178c6; }
@media (prefers-color-scheme: dark) { :root { --color-info: #60a5fa; } }
```
Then use in components:
```css
.alert-info { background: rgba(var(--color-info-rgb, 49,120,198), 0.12); color: var(--color-info); }
```
(Add an `--color-info-rgb` token if you require alpha blending.)

## Programmatic override
You can force a theme in code:
```js
import { useSystemTheme } from './hooks/useSystemTheme';
// ...
const { setThemePreference } = useSystemTheme();
setThemePreference('dark'); // or 'light' or 'system'
```

To reset to system default:
```js
setThemePreference('system');
```

## Accessibility notes
- Ensure contrast ratio ≥ 4.5:1 for body text. The dark palette uses elevated accent/success/warning/error shades for contrast.
- Focus styles rely on `--color-focus-ring`; adjust if you change accent hues.
- Avoid conveying meaning by color alone; pair icons or text where possible.

## Component migration checklist
1. Replace hard-coded colors with variables (search for `#` or `rgb(` occurrences).
2. For subtle backgrounds (badges, status, pills) use alpha over a semantic rgb triple: `rgba(var(--color-success-rgb), 0.12)`.
3. Test in both themes: temporarily toggle via Theme Selector in Settings.
4. Verify focus ring visibility in both modes.

## Future enhancements
- Persist theme preference to a backend profile per user (if auth is added).
- Add high-contrast theme variant.
- Animated cross-fade between themes using `prefers-reduced-motion` guard.

---
Maintainers: Keep `theme.css` small and semantic. If design grows, consider grouping variables (e.g., layout, typography, color) or using a build step to generate tokens.
