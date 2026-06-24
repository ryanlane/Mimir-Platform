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

import { useCallback, useEffect, useState } from 'react';
import { outbox } from '../services/outbox';

export function useOutbox() {
  const [count, setCount] = useState(0);
  const refresh = useCallback(() => {
    outbox.list().then(items => {
      setCount(items.filter(i => i.status === 'pending' || i.status === 'sending').length);
    });
  }, []);

  useEffect(() => {
    refresh();
    const handler = () => refresh();
    window.addEventListener('mimir:outbox-updated', handler);
    return () => window.removeEventListener('mimir:outbox-updated', handler);
  }, [refresh]);

  const enqueue = useCallback(async (payload) => {
    const id = await outbox.enqueue(payload);
    refresh();
    return id;
  }, [refresh]);

  const forceFlush = useCallback(async () => {
    if (navigator.serviceWorker?.controller) {
      navigator.serviceWorker.controller.postMessage({ type: 'OUTBOX_FLUSH' });
    } else {
      await outbox.forceFlush();
      refresh();
    }
  }, [refresh]);

  return { count, enqueue, refresh, forceFlush };
}

export default useOutbox;
