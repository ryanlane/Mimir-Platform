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
