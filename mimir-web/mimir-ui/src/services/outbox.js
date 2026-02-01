// Outbox queue service for offline mutation handling
// Provides enqueue, list, flush (inline), and helpers. SW will message clients on success/failure.

import { idb } from './idb';

const MAX_ATTEMPTS = 8;
const BACKOFF_BASE_MS = 2000;

function calcNextAttempt(attemptCount) {
  const expo = Math.min(attemptCount - 1, 6); // cap growth
  return Date.now() + BACKOFF_BASE_MS * Math.pow(2, expo);
}

export const outbox = {
  async enqueue({ url, method = 'POST', body = null, headers = {}, optimistic = null }) {
    const item = {
      id: crypto.randomUUID(),
      url,
      method,
      body,
      headers,
      optimistic,
      attempt_count: 0,
      created_at: Date.now(),
      next_attempt_at: Date.now(),
      status: 'pending'
    };
    await idb.add(idb.STORES.OUTBOX, item);
    window.dispatchEvent(new CustomEvent('mimir:outbox-updated'));
    return item.id;
  },
  async list() {
    return idb.getAll(idb.STORES.OUTBOX);
  },
  async remove(id) {
    return idb.delete(idb.STORES.OUTBOX, id);
  },
  async update(id, patch) {
    const existing = await idb.get(idb.STORES.OUTBOX, id);
    if (!existing) return;
    const updated = { ...existing, ...patch };
    await idb.set(idb.STORES.OUTBOX, id, updated);
  },
  async nextEligibleBatch(limit = 25) {
    const all = await idb.getAll(idb.STORES.OUTBOX);
    const now = Date.now();
    return all
      .filter(i => i.status === 'pending' && i.next_attempt_at <= now)
      .sort((a, b) => a.created_at - b.created_at)
      .slice(0, limit);
  },
  async flushOnce(fetchImpl = fetch) {
    const batch = await this.nextEligibleBatch();
    for (const item of batch) {
      try {
        await this.update(item.id, { status: 'sending', last_attempt_at: Date.now() });
        const res = await fetchImpl(item.url, {
          method: item.method,
            headers: { 'Content-Type': 'application/json', ...item.headers },
            body: item.body ? JSON.stringify(item.body) : undefined
        });
        if (!res.ok) {
          if (res.status >= 400 && res.status < 500 && res.status !== 429) {
            await this.update(item.id, { status: 'dead-letter', http_status: res.status });
            continue;
          }
          throw new Error('HTTP ' + res.status);
        }
        await this.remove(item.id);
        window.dispatchEvent(new CustomEvent('mimir:outbox-item-sent', { detail: { id: item.id } }));
      } catch (e) {
        const attempts = item.attempt_count + 1;
        if (attempts >= MAX_ATTEMPTS) {
          await this.update(item.id, { status: 'dead-letter', error: e.message, attempt_count: attempts });
        } else {
          await this.update(item.id, {
            status: 'pending',
            attempt_count: attempts,
            next_attempt_at: calcNextAttempt(attempts)
          });
        }
      }
    }
    window.dispatchEvent(new CustomEvent('mimir:outbox-updated'));
  },
  async forceFlush() {
    await this.flushOnce();
  }
};

export default outbox;
