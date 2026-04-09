import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { useSceneFormLogic } from '../useSceneFormLogic';
import { api } from '../../../services/api';

// Mock api module
jest.mock('../../../services/api', () => ({
  api: {
    getChannelManifest: jest.fn().mockResolvedValue({ data: { capabilities: { update_modes: ['push'] } } }),
    getSubChannels: jest.fn().mockResolvedValue({ data: [] }),
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

  it('refreshes live subchannels when loading channel capabilities', async () => {
    api.getChannelManifest.mockResolvedValueOnce({
      data: {
        galleries: [{ id: 'test', name: 'Test', image_count: 1 }],
        capabilities: { supports_gallery: true, update_modes: ['push'] }
      }
    });
    api.getSubChannels.mockResolvedValueOnce({
      data: [
        { id: 'test', name: 'Test', image_count: 1 },
        { id: 'foo', name: 'Foo', image_count: 0 }
      ]
    });

    render(<TestHarness scene={null} channels={[{ id: 'photo', name: 'Photo' }]} />);

    await waitFor(() => {
      expect(api.getChannelManifest).toHaveBeenCalledWith('photo', { forceRefresh: true });
      expect(api.getSubChannels).toHaveBeenCalledWith('photo', { forceRefresh: true });
    });
  });
});
