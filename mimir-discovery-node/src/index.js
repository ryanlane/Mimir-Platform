import process from 'node:process'
import os from 'node:os'

function env(name, def) {
  const v = process.env[name]
  return v == null || v === '' ? def : v
}

function truthy(v) {
  if (v == null) return false
  const s = String(v).trim().toLowerCase()
  return ['1', 'true', 'yes', 'y', 'on'].includes(s)
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

function isoNow() {
  return new Date().toISOString()
}

function parseInterfaceList(v) {
  if (v == null) return null
  const s = String(v).trim()
  if (!s) return null
  const parts = s
    .split(',')
    .map((p) => p.trim())
    .filter(Boolean)
  return parts.length ? parts : null
}

function toServiceName(svc) {
  if (svc.fqdn && typeof svc.fqdn === 'string') return svc.fqdn
  const name = svc.name || 'unknown'
  // Keep it close to what avahi-browse prints:
  return `${name}._mimir-display._tcp.local.`
}

function toProperties(txt) {
  const props = {}
  if (!txt || typeof txt !== 'object') return props
  for (const [k, v] of Object.entries(txt)) {
    if (v == null) continue
    props[String(k)] = typeof v === 'string' ? v : String(v)
  }
  return props
}

function parseWebhookPort(svc, props) {
  const fromTxt = props.webhook_port || props.webhookPort
  if (fromTxt) {
    const n = Number.parseInt(String(fromTxt), 10)
    if (Number.isFinite(n) && n > 0) return n
  }
  const n = Number.parseInt(String(svc.port || ''), 10)
  return Number.isFinite(n) && n > 0 ? n : null
}

async function postBatch({ apiBase, token, events }) {
  const url = `${apiBase.replace(/\/$/, '')}/api/displays/mdns/ingest`
  const headers = { 'content-type': 'application/json' }
  if (token) headers['x-mimir-discovery-token'] = token

  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ events })
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`ingest failed ${res.status}: ${text.slice(0, 200)}`)
  }
}

async function main() {
  const apiBase = env('MIMIR_API_BASE', 'http://127.0.0.1:5000')
  const token = env('MIMIR_DISCOVERY_TOKEN', '') || null
  const batchMs = Number.parseInt(env('MIMIR_BATCH_MS', '1000'), 10)
  const type = env('MIMIR_MDNS_TYPE', 'mimir-display')
  const protocol = env('MIMIR_MDNS_PROTOCOL', 'tcp')
  const logLevel = env('LOG_LEVEL', 'info').toLowerCase()
  const debug = logLevel === 'debug'
  const browseAll = truthy(env('MIMIR_BROWSE_ALL', 'false'))
  const statsEveryMs = Number.parseInt(env('MIMIR_STATS_MS', '10000'), 10)
  const mdnsInterface = parseInterfaceList(env('MIMIR_MDNS_INTERFACE', ''))
  const mdnsPort = Number.parseInt(env('MIMIR_MDNS_PORT', ''), 10)

  if (debug) {
    const nics = os.networkInterfaces()
    console.log('[discovery] nics', nics)
  }

  const { Bonjour } = await import('bonjour-service')
  const bonjour = new Bonjour(
    {
      ...(mdnsInterface ? { interface: mdnsInterface.length === 1 ? mdnsInterface[0] : mdnsInterface } : {}),
      ...(Number.isFinite(mdnsPort) && mdnsPort > 0 ? { port: mdnsPort } : {}),
    },
    (err) => {
      const msg = err instanceof Error ? err.message : String(err)
      console.warn('[discovery] mdns error:', msg)
    }
  )

  const pending = []
  let lastFlush = Date.now()
  let seenCount = 0
  let postedCount = 0
  let lastPostOkAt = null

  function enqueue(event) {
    pending.push(event)
    seenCount += 1
    if (debug) {
      const { event: ev, service_name, webhook_port, addresses } = event
      console.log('[discovery] event', ev, service_name, { webhook_port, addresses })
    }
  }

  async function flushIfDue() {
    if (pending.length === 0) return
    if ((Date.now() - lastFlush) < batchMs) return

    const events = pending.splice(0, pending.length)
    try {
      await postBatch({ apiBase, token, events })
      postedCount += events.length
      lastPostOkAt = Date.now()
      if (debug) console.log('[discovery] posted', events.length)
    } catch (e) {
      // Best-effort: requeue (bounded) and try again later
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[discovery] post failed:', msg)
      // Prevent unbounded growth
      while (pending.length + events.length > 2000) pending.shift()
      pending.unshift(...events)
    } finally {
      lastFlush = Date.now()
    }
  }

  const query = browseAll ? {} : { type, protocol }
  const browser = bonjour.find(query)

  browser.on('up', (svc) => {
    if (debug && browseAll) {
      console.log('[discovery] up(raw)', {
        name: svc?.name,
        type: svc?.type,
        protocol: svc?.protocol,
        fqdn: svc?.fqdn,
        host: svc?.host,
        port: svc?.port,
      })
    }

    if (browseAll) {
      // When browsing all, only ingest the mimir-display service type.
      if (svc?.type !== type || svc?.protocol !== protocol) return
    }

    const props = toProperties(svc.txt)
    const service_name = toServiceName(svc)
    const webhook_port = parseWebhookPort(svc, props)
    const addresses = Array.isArray(svc.addresses) ? svc.addresses : []

    enqueue({
      event: 'discovered',
      service_name,
      properties: props,
      addresses,
      webhook_port,
      seen_at: isoNow()
    })
  })

  browser.on('down', (svc) => {
    if (browseAll) {
      if (svc?.type !== type || svc?.protocol !== protocol) return
    }
    const service_name = toServiceName(svc)
    enqueue({ event: 'lost', service_name, seen_at: isoNow() })
  })

  // Treat TXT updates as a "discovered" refresh so the API cache stays current.
  browser.on('txt-update', (svc) => {
    if (browseAll) {
      if (svc?.type !== type || svc?.protocol !== protocol) return
    }
    const props = toProperties(svc.txt)
    const service_name = toServiceName(svc)
    const webhook_port = parseWebhookPort(svc, props)
    const addresses = Array.isArray(svc.addresses) ? svc.addresses : []

    enqueue({
      event: 'updated',
      service_name,
      properties: props,
      addresses,
      webhook_port,
      seen_at: isoNow()
    })
  })

  const shutdown = async () => {
    try { browser.stop() } catch {}
    try { bonjour.destroy() } catch {}
    try {
      // flush one last time
      await postBatch({ apiBase, token, events: pending.splice(0, pending.length) })
    } catch {}
    process.exit(0)
  }

  process.on('SIGINT', shutdown)
  process.on('SIGTERM', shutdown)

  console.log('[discovery] started', {
    apiBase,
    type,
    protocol,
    batchMs,
    token: token ? 'set' : 'unset',
    browseAll,
    logLevel,
    mdnsInterface: mdnsInterface || 'auto',
    mdnsPort: Number.isFinite(mdnsPort) && mdnsPort > 0 ? mdnsPort : 'default',
  })

  let lastStats = Date.now()
  let lastBrowseUpdate = Date.now()
  const browseUpdateEveryMs = Number.parseInt(env('MIMIR_BROWSE_UPDATE_MS', '30000'), 10)

  // Periodic flush loop
  // eslint-disable-next-line no-constant-condition
  while (true) {
    await sleep(200)
    await flushIfDue()

    if (Number.isFinite(browseUpdateEveryMs) && browseUpdateEveryMs > 0) {
      if ((Date.now() - lastBrowseUpdate) >= browseUpdateEveryMs) {
        try { browser.update() } catch {}
        lastBrowseUpdate = Date.now()
      }
    }

    if (statsEveryMs > 0 && (Date.now() - lastStats) >= statsEveryMs) {
      console.log('[discovery] stats', {
        pending: pending.length,
        lastFlushMsAgo: Date.now() - lastFlush,
        seenCount,
        postedCount,
        lastPostOkMsAgo: lastPostOkAt ? (Date.now() - lastPostOkAt) : null,
        query: browseAll ? 'all' : { type, protocol },
      })
      lastStats = Date.now()
    }
  }
}

main().catch((e) => {
  const msg = e instanceof Error ? e.stack || e.message : String(e)
  console.error('[discovery] fatal:', msg)
  process.exit(1)
})
