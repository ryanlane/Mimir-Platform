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
