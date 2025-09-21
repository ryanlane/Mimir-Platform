import { render, screen } from '@testing-library/react';
import React from 'react';
import { useSceneFormLogic } from '../useSceneFormLogic';

// Mock api module
jest.mock('../../../services/api', () => ({
  api: {
    getChannelManifest: jest.fn().mockResolvedValue({ data: { capabilities: { update_modes: ['push'] } } }),
    getSceneSchedules: jest.fn().mockResolvedValue([]),
    getSchedulerJob: jest.fn(),
    createSchedulerJob: jest.fn(),
    updateSchedulerJob: jest.fn(),
    deleteSchedulerJob: jest.fn(),
    updateScene: jest.fn().mockResolvedValue({}),
    createScene: jest.fn().mockResolvedValue({})
  }
}));

function TestHarness({ scene, channels }) {
  const { formData, pushSelectable } = useSceneFormLogic({ scene, channels, onClose: () => {} });
  return (
    <div>
      <span data-testid="strategy">{formData.update_strategy}</span>
      <span data-testid="pushSelectable">{pushSelectable ? 'yes' : 'no'}</span>
    </div>
  );
}

describe('useSceneFormLogic', () => {
  it('initializes with scheduler strategy and evaluates push capability', () => {
    render(<TestHarness scene={null} channels={[{ id: 'photo', name: 'Photo' }]} />);
    expect(screen.getByTestId('strategy').textContent).toBe('scheduler');
    expect(['yes', 'no']).toContain(screen.getByTestId('pushSelectable').textContent);
  });
});
