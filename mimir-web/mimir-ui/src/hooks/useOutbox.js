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
