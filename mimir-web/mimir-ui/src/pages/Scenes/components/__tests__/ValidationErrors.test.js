import { render, screen } from '@testing-library/react';
import ValidationErrors from '../ValidationErrors';

describe('ValidationErrors', () => {
  it('renders nothing when empty', () => {
    render(<ValidationErrors errors={[]} />);
    // heading should not appear
    expect(screen.queryByText(/Validation Errors/i)).toBeNull();
  });
  it('renders list items when errors present', () => {
    render(<ValidationErrors errors={['One', 'Two']} />);
    expect(screen.getByText('One')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem').length).toBe(2);
  });
});
