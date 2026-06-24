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

import { render, screen, fireEvent } from '@testing-library/react';
import DistributionModeSelector from '../DistributionModeSelector';

describe('DistributionModeSelector', () => {
  it('renders all modes and selects current', () => {
    const handle = jest.fn();
    render(<DistributionModeSelector value="MIRROR" onChange={handle} />);
    expect(screen.getByLabelText(/Mirror Mode/i)).toBeInTheDocument();
  expect(screen.getByDisplayValue('MIRROR')).toBeChecked();
  });

  it('calls onChange when mode clicked', () => {
    const handle = jest.fn();
    render(<DistributionModeSelector value="MIRROR" onChange={handle} />);
    fireEvent.click(screen.getByDisplayValue('SEQUENTIAL'));
    expect(handle).toHaveBeenCalledWith('SEQUENTIAL');
  });
});
