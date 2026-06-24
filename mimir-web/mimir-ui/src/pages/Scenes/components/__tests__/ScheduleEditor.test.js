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
import ScheduleEditor from '../ScheduleEditor';

describe('ScheduleEditor', () => {
  it('renders create schedule form when no schedule', () => {
    render(<ScheduleEditor currentSchedule={null} scheduleData={{ freq_unit: 'hour', freq_value: 1, enabled: true }} scheduleModified={false} loading={false} sceneId={1} onChange={() => {}} onCreate={() => {}} onUpdate={() => {}} onDelete={() => {}} />);
    expect(screen.getByText(/Add Schedule/i)).toBeInTheDocument();
  });
  it('renders existing schedule when provided', () => {
    const current = { id: 5, freq_unit: 'hour', freq_value: 2, enabled: true };
    render(<ScheduleEditor currentSchedule={current} scheduleData={{ freq_unit: 'hour', freq_value: 2, enabled: true }} scheduleModified={false} loading={false} sceneId={1} onChange={() => {}} onCreate={() => {}} onUpdate={() => {}} onDelete={() => {}} />);
    expect(screen.getByText(/Current: Every 2 hour/i)).toBeInTheDocument();
  });
  it('calls onChange when value edited', () => {
    const handle = jest.fn();
    render(<ScheduleEditor currentSchedule={null} scheduleData={{ freq_unit: 'hour', freq_value: 1, enabled: true }} scheduleModified={false} loading={false} sceneId={1} onChange={handle} onCreate={() => {}} onUpdate={() => {}} onDelete={() => {}} />);
    fireEvent.change(screen.getByDisplayValue('1'), { target: { value: '3' } });
    expect(handle).toHaveBeenCalled();
  });
});
