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

import { render, screen } from '@testing-library/react';
import UpdateStrategySelector from '../UpdateStrategySelector';

describe('UpdateStrategySelector', () => {
  it('disables push when not allowed', () => {
    render(<UpdateStrategySelector strategy="scheduler" fallbackSeconds={120} pushAllowed={false} hasChannelSelected={true} onChange={() => {}} />);
    const pushRadio = screen.getByDisplayValue('push');
    expect(pushRadio).toBeDisabled();
  });

  it('shows fallback input when push selected', () => {
    render(<UpdateStrategySelector strategy="push" fallbackSeconds={150} pushAllowed={true} hasChannelSelected={true} onChange={() => {}} />);
    expect(screen.getByLabelText(/Fallback Poll Interval/i)).toBeInTheDocument();
  });
});
