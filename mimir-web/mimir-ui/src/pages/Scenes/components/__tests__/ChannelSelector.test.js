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
import ChannelSelector from '../ChannelSelector';

describe('ChannelSelector', () => {
  const channels = [{ id: 'photo', name: 'Photo Frame' }, { id: 'news', name: 'News' }];

  it('selects and deselects a channel (single)', () => {
    let assignments = [];
    const handle = (a) => { assignments = a; };
    const { rerender } = render(
      <ChannelSelector
        channels={channels}
        assignments={assignments}
        subChannelSupport={{ photo: false, news: false }}
        availableSubChannels={{}}
        subChannelRequirements={{}}
        loadingSubChannels={false}
        onChange={handle}
      />
    );
    fireEvent.click(screen.getByLabelText(/Photo Frame/i));
    rerender(
      <ChannelSelector
        channels={channels}
        assignments={assignments}
        subChannelSupport={{ photo: false, news: false }}
        availableSubChannels={{}}
        subChannelRequirements={{}}
        loadingSubChannels={false}
        onChange={handle}
      />
    );
    expect(assignments.length).toBe(1);
    fireEvent.click(screen.getByLabelText(/Photo Frame/i));
    rerender(
      <ChannelSelector
        channels={channels}
        assignments={assignments}
        subChannelSupport={{ photo: false, news: false }}
        availableSubChannels={{}}
        subChannelRequirements={{}}
        loadingSubChannels={false}
        onChange={handle}
      />
    );
    expect(assignments.length).toBe(0);
  });
});
