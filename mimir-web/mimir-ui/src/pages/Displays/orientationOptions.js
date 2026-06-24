// Copyright (C) 2026 Ryan Lane
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published
// by the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

export const ORIENTATION_OPTIONS = [
  { value: 'landscape', label: 'Landscape' },
  { value: 'landscape_inverted', label: 'Landscape (Upside Down)' },
  { value: 'portrait_right', label: 'Portrait (Rotate Right)' },
  { value: 'portrait_left', label: 'Portrait (Rotate Left)' },
  { value: 'square', label: 'Square' },
];

const ORIENTATION_LABELS = Object.fromEntries(
  ORIENTATION_OPTIONS.map(({ value, label }) => [value, label])
);

const ORIENTATION_ALIASES = {
  landscape_up: 'landscape',
  landscape_down: 'landscape_inverted',
  portrait: 'portrait_right',
  portrait_up: 'portrait_right',
  portrait_down: 'portrait_left',
};

export const normalizeOrientationValue = (value) => {
  const normalized = String(value || 'landscape').trim().toLowerCase();
  return ORIENTATION_ALIASES[normalized] || normalized || 'landscape';
};

export const formatOrientationLabel = (value) => {
  const normalized = normalizeOrientationValue(value);
  return ORIENTATION_LABELS[normalized] || 'Landscape';
};

export const getOrientationOptionsForDisplay = (display) => {
  const resolution = Array.isArray(display?.resolution) && display.resolution.length >= 2
    ? display.resolution
    : [display?.width, display?.height];
  const width = Number(resolution?.[0] || 0);
  const height = Number(resolution?.[1] || 0);
  const normalized = normalizeOrientationValue(display?.orientation);
  const isSquareDisplay = (width > 0 && height > 0 && width === height) || normalized === 'square';

  if (isSquareDisplay) {
    return ORIENTATION_OPTIONS.filter((option) => option.value === 'square');
  }

  return ORIENTATION_OPTIONS.filter((option) => option.value !== 'square');
};