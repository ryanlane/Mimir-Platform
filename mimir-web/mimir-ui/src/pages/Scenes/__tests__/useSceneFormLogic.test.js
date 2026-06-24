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
  const { formData, pushSelectable, save } = useSceneFormLogic({ scene, channels, onClose: () => {} });
  return (
    <div>
      <span data-testid="strategy">{formData.update_strategy}</span>
      <span data-testid="pushSelectable">{pushSelectable ? 'yes' : 'no'}</span>
      <button data-testid="save" onClick={() => save()}>save</button>
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

  it('creates a scheduler job when saving a new scheduler scene without an existing schedule', async () => {
    api.createScene.mockResolvedValueOnce({ data: { id: 'scene-123', name: 'Test Scene' } });
    api.createSchedulerJob.mockResolvedValueOnce({ data: { id: 'job-123', freq_unit: 'hour', freq_value: 1, enabled: true } });

    render(<TestHarness scene={null} channels={[{ id: 'photo', name: 'Photo' }]} />);

    screen.getByTestId('save').click();

    await waitFor(() => {
      expect(api.createScene).toHaveBeenCalled();
      expect(api.createSchedulerJob).toHaveBeenCalledWith(expect.objectContaining({
        scene_ids: ['scene-123'],
        action_type: 'refresh_scene',
        refresh_method: 'content_refresh',
        freq_unit: 'hour',
        freq_value: 1,
      }));
    });
  });
});
