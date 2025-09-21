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
