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
