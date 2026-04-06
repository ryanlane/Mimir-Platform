using System.Collections.Concurrent;
using System.Text.Json;
using System.Text.Json.Serialization;
using Zeroconf;

static string Env(string name, string def)
{
    var v = Environment.GetEnvironmentVariable(name);
    return string.IsNullOrWhiteSpace(v) ? def : v.Trim();
}

static bool Truthy(string? v)
{
    if (string.IsNullOrWhiteSpace(v)) return false;
    var s = v.Trim().ToLowerInvariant();
    return s is "1" or "true" or "yes" or "y" or "on";
}

static int EnvInt(string name, int def)
{
    var v = Environment.GetEnvironmentVariable(name);
    return int.TryParse(v, out var n) ? n : def;
}

static string IsoNow() => DateTimeOffset.UtcNow.ToString("O");

static string NormalizeServiceType(string type, string protocol)
{
    var t = type.StartsWith("_") ? type : "_" + type;
    var p = protocol.StartsWith("_") ? protocol : "_" + protocol;
    return $"{t}.{p}.local.";
}

static Dictionary<string, string> ToProperties(object? properties)
{
    var output = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    if (properties is null) return output;

    if (properties is IReadOnlyDictionary<string, string> kvpString)
    {
        foreach (var kv in kvpString) output[kv.Key] = kv.Value ?? string.Empty;
        return output;
    }

    if (properties is IReadOnlyDictionary<string, IReadOnlyList<string>> kvpList)
    {
        foreach (var kv in kvpList) output[kv.Key] = string.Join(",", kv.Value ?? Array.Empty<string>());
        return output;
    }

    if (properties is IReadOnlyDictionary<string, string[]> kvpArray)
    {
        foreach (var kv in kvpArray) output[kv.Key] = string.Join(",", kv.Value ?? Array.Empty<string>());
        return output;
    }

    return output;
}

static void EnsureDisplayIdentity(Dictionary<string, string> props, string instanceName, string hostName)
{
    if (string.IsNullOrWhiteSpace(instanceName)) return;

    var derivedId = instanceName;
    if (instanceName.StartsWith("mimir-display-", StringComparison.OrdinalIgnoreCase))
    {
        derivedId = instanceName.Substring("mimir-display-".Length);
    }
    derivedId = derivedId.Trim().TrimEnd('.');

    if (!props.ContainsKey("display_id") && !string.IsNullOrWhiteSpace(derivedId))
    {
        props["display_id"] = derivedId;
    }
    if (!props.ContainsKey("display_name") && !string.IsNullOrWhiteSpace(derivedId))
    {
        props["display_name"] = $"Display ({derivedId})";
    }
    if (!props.ContainsKey("hostname") && !string.IsNullOrWhiteSpace(hostName))
    {
        props["hostname"] = hostName;
    }
}

static int? ParseWebhookPort(IDictionary<string, string> props, int? fallback)
{
    if (props.TryGetValue("webhook_port", out var raw) || props.TryGetValue("webhookPort", out raw))
    {
        if (int.TryParse(raw, out var n) && n > 0) return n;
    }
    return fallback is > 0 ? fallback : null;
}

static bool DictionariesEqual(IReadOnlyDictionary<string, string> a, IReadOnlyDictionary<string, string> b)
{
    if (a.Count != b.Count) return false;
    foreach (var kv in a)
    {
        if (!b.TryGetValue(kv.Key, out var val)) return false;
        if (!string.Equals(kv.Value, val, StringComparison.Ordinal)) return false;
    }
    return true;
}

static bool ListsEqual(IReadOnlyList<string> a, IReadOnlyList<string> b)
{
    if (a.Count != b.Count) return false;
    for (var i = 0; i < a.Count; i++)
    {
        if (!string.Equals(a[i], b[i], StringComparison.OrdinalIgnoreCase)) return false;
    }
    return true;
}

var apiBase = Env("MIMIR_API_BASE", "http://127.0.0.1:5000");
var token = Env("MIMIR_DISCOVERY_TOKEN", string.Empty);
var batchMs = EnvInt("MIMIR_BATCH_MS", 1000);
var type = Env("MIMIR_MDNS_TYPE", "mimir-display");
var protocol = Env("MIMIR_MDNS_PROTOCOL", "tcp");
var logLevel = Env("LOG_LEVEL", "info").ToLowerInvariant();
var debug = logLevel == "debug";
var browseAll = Truthy(Environment.GetEnvironmentVariable("MIMIR_BROWSE_ALL"));
var statsEveryMs = EnvInt("MIMIR_STATS_MS", 10000);
var browseUpdateMs = EnvInt("MIMIR_BROWSE_UPDATE_MS", 30000);
var scanCount = EnvInt("MIMIR_MDNS_SCAN_COUNT", 2);
var scanDelayMs = EnvInt("MIMIR_MDNS_SCAN_DELAY_MS", 200);
var scanTimeMs = EnvInt("MIMIR_MDNS_SCAN_TIME_MS", 2000);
var mdnsInterface = Env("MIMIR_MDNS_INTERFACE", string.Empty);
var mdnsPort = EnvInt("MIMIR_MDNS_PORT", 0);

if (browseAll)
{
    Console.WriteLine("[discovery] note: browse-all is not supported in the .NET agent; using MIMIR_MDNS_TYPE/PROTOCOL instead.");
    browseAll = false;
}

var serviceType = NormalizeServiceType(type, protocol);

var pending = new ConcurrentQueue<DiscoveryEvent>();
var lastFlush = DateTimeOffset.UtcNow;
var lastStats = DateTimeOffset.UtcNow;
var lastScan = DateTimeOffset.MinValue;

var seenCount = 0;
var postedCount = 0;
DateTimeOffset? lastPostOkAt = null;

using var http = new HttpClient();
http.Timeout = TimeSpan.FromSeconds(10);

var jsonOptions = new JsonSerializerOptions
{
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
};

var snapshots = new Dictionary<string, ServiceSnapshot>(StringComparer.OrdinalIgnoreCase);

using var cts = new CancellationTokenSource();
Console.CancelKeyPress += (_, e) =>
{
    e.Cancel = true;
    cts.Cancel();
};

Console.WriteLine("[discovery] started");
Console.WriteLine($"  apiBase={apiBase}");
Console.WriteLine($"  serviceType={serviceType}");
Console.WriteLine($"  batchMs={batchMs}");
Console.WriteLine($"  browseUpdateMs={browseUpdateMs}");
Console.WriteLine($"  statsMs={statsEveryMs}");
Console.WriteLine($"  scanCount={scanCount} scanDelayMs={scanDelayMs}");
Console.WriteLine($"  scanTimeMs={scanTimeMs}");
Console.WriteLine($"  token={(string.IsNullOrWhiteSpace(token) ? "unset" : "set")}");
if (!string.IsNullOrWhiteSpace(mdnsInterface)) Console.WriteLine($"  mdnsInterface={mdnsInterface}");
if (mdnsPort > 0) Console.WriteLine($"  mdnsPort={mdnsPort}");

async Task PostBatchAsync(List<DiscoveryEvent> events)
{
    if (events.Count == 0) return;
    var url = apiBase.TrimEnd('/') + "/api/displays/mdns/ingest";
    using var req = new HttpRequestMessage(HttpMethod.Post, url);
    if (!string.IsNullOrWhiteSpace(token)) req.Headers.Add("x-mimir-discovery-token", token);

    var payload = new IngestPayload { Events = events };
    req.Content = new StringContent(JsonSerializer.Serialize(payload, jsonOptions), System.Text.Encoding.UTF8, "application/json");

    using var res = await http.SendAsync(req, cts.Token);
    if (!res.IsSuccessStatusCode)
    {
        var text = await res.Content.ReadAsStringAsync(cts.Token);
        throw new InvalidOperationException($"ingest failed {(int)res.StatusCode}: {text[..Math.Min(text.Length, 200)]}");
    }
}

async Task FlushIfDueAsync()
{
    if (pending.IsEmpty) return;
    if ((DateTimeOffset.UtcNow - lastFlush).TotalMilliseconds < batchMs) return;

    var batch = new List<DiscoveryEvent>();
    while (pending.TryDequeue(out var ev)) batch.Add(ev);

    try
    {
        await PostBatchAsync(batch);
        postedCount += batch.Count;
        lastPostOkAt = DateTimeOffset.UtcNow;
        if (debug) Console.WriteLine($"[discovery] posted {batch.Count}");
    }
    catch (Exception ex)
    {
        Console.WriteLine($"[discovery] post failed: {ex.Message}");
        // Requeue bounded
        foreach (var ev in batch.Take(2000)) pending.Enqueue(ev);
    }
    finally
    {
        lastFlush = DateTimeOffset.UtcNow;
    }
}

void Enqueue(DiscoveryEvent ev)
{
    pending.Enqueue(ev);
    seenCount++;
    if (debug)
    {
        Console.WriteLine($"[discovery] event {ev.Event} {ev.ServiceName}");
    }
}

async Task<Dictionary<string, ServiceSnapshot>> ScanAsync()
{
    var output = new Dictionary<string, ServiceSnapshot>(StringComparer.OrdinalIgnoreCase);

    var scans = Math.Max(1, scanCount);
    for (var i = 0; i < scans; i++)
    {
        var results = await ResolveWithOptionsAsync(serviceType, scanTimeMs, scans);
        foreach (var host in results)
        {
            var addresses = new List<string>();
            if (!string.IsNullOrWhiteSpace(host.IPAddress)) addresses.Add(host.IPAddress);
            addresses.Sort(StringComparer.OrdinalIgnoreCase);

            foreach (var svc in host.Services.Values)
            {
                var instance = svc.Name ?? host.DisplayName ?? host.Id ?? "unknown";
                var serviceName = instance.Contains("._", StringComparison.Ordinal) ? instance : $"{instance}.{serviceType}";
                var props = ToProperties(svc.Properties);
                EnsureDisplayIdentity(props, instance, host.DisplayName ?? host.Id ?? string.Empty);
                var webhookPort = ParseWebhookPort(props, svc.Port);

                var snapshot = new ServiceSnapshot(
                    serviceName,
                    webhookPort,
                    addresses,
                    props
                );

                output[serviceName] = snapshot;
            }
        }

        if (i < scans - 1)
        {
            await Task.Delay(Math.Max(0, scanDelayMs));
        }
    }

    return output;
}

async Task<IReadOnlyList<IZeroconfHost>> ResolveWithOptionsAsync(string type, int scanMs, int retries)
{
    try
    {
        var resolverType = typeof(ZeroconfResolver);
        var optsType = resolverType.Assembly.GetType("Zeroconf.ResolveOptions");
        if (optsType != null)
        {
            var opts = Activator.CreateInstance(optsType);
            var scanProp = optsType.GetProperty("ScanTime");
            if (scanProp?.PropertyType == typeof(TimeSpan))
            {
                scanProp.SetValue(opts, TimeSpan.FromMilliseconds(Math.Max(500, scanMs)));
            }
            var retriesProp = optsType.GetProperty("Retries");
            if (retriesProp?.PropertyType == typeof(int))
            {
                retriesProp.SetValue(opts, Math.Max(1, retries));
            }

            var method = resolverType
                .GetMethods()
                .FirstOrDefault(m =>
                {
                    if (m.Name != "ResolveAsync") return false;
                    var p = m.GetParameters();
                    return p.Length >= 2 && p[0].ParameterType == typeof(string) && p[1].ParameterType == optsType;
                });

            if (method != null)
            {
                var parameters = method.GetParameters().Length switch
                {
                    2 => new object?[] { type, opts },
                    3 => new object?[] { type, opts, CancellationToken.None },
                    _ => new object?[] { type, opts }
                };
                dynamic task = method.Invoke(null, parameters)!;
                var results = await task;
                return results;
            }
        }
    }
    catch
    {
        // fall back below
    }

    return await ZeroconfResolver.ResolveAsync(type);
}

while (!cts.IsCancellationRequested)
{
    if ((DateTimeOffset.UtcNow - lastScan).TotalMilliseconds >= browseUpdateMs)
    {
        var current = await ScanAsync();

        foreach (var kv in current)
        {
            if (!snapshots.TryGetValue(kv.Key, out var prev))
            {
                Enqueue(DiscoveryEvent.FromSnapshot("discovered", kv.Value));
                continue;
            }

            if (prev.WebhookPort != kv.Value.WebhookPort ||
                !ListsEqual(prev.Addresses, kv.Value.Addresses) ||
                !DictionariesEqual(prev.Properties, kv.Value.Properties))
            {
                Enqueue(DiscoveryEvent.FromSnapshot("updated", kv.Value));
            }
        }

        foreach (var kv in snapshots)
        {
            if (!current.ContainsKey(kv.Key))
            {
                Enqueue(new DiscoveryEvent
                {
                    Event = "lost",
                    ServiceName = kv.Key,
                    SeenAt = IsoNow()
                });
            }
        }

        snapshots = current;
        lastScan = DateTimeOffset.UtcNow;
    }

    await FlushIfDueAsync();

    if (statsEveryMs > 0 && (DateTimeOffset.UtcNow - lastStats).TotalMilliseconds >= statsEveryMs)
    {
        var lastOkMs = lastPostOkAt.HasValue ? (DateTimeOffset.UtcNow - lastPostOkAt.Value).TotalMilliseconds : (double?)null;
        Console.WriteLine("[discovery] stats" +
            $" pending={pending.Count} lastFlushMsAgo={(DateTimeOffset.UtcNow - lastFlush).TotalMilliseconds:0}" +
            $" seenCount={seenCount} postedCount={postedCount} lastPostOkMsAgo={(lastOkMs.HasValue ? lastOkMs.Value.ToString("0") : "null")}");
        lastStats = DateTimeOffset.UtcNow;
    }

    await Task.Delay(200, cts.Token);
}

// Final flush on shutdown
try
{
    var finalBatch = new List<DiscoveryEvent>();
    while (pending.TryDequeue(out var ev)) finalBatch.Add(ev);
    await PostBatchAsync(finalBatch);
}
catch
{
    // ignore
}

return;

record ServiceSnapshot(
    string ServiceName,
    int? WebhookPort,
    IReadOnlyList<string> Addresses,
    IReadOnlyDictionary<string, string> Properties
);

sealed class IngestPayload
{
    [JsonPropertyName("events")]
    public List<DiscoveryEvent> Events { get; init; } = new();
}

sealed class DiscoveryEvent
{
    private static string NowIso() => DateTimeOffset.UtcNow.ToString("O");

    [JsonPropertyName("event")]
    public string Event { get; set; } = "discovered";

    [JsonPropertyName("service_name")]
    public string ServiceName { get; set; } = "";

    [JsonPropertyName("properties")]
    public Dictionary<string, string>? Properties { get; set; }

    [JsonPropertyName("addresses")]
    public List<string>? Addresses { get; set; }

    [JsonPropertyName("webhook_port")]
    public int? WebhookPort { get; set; }

    [JsonPropertyName("seen_at")]
    public string SeenAt { get; set; } = "";

    public static DiscoveryEvent FromSnapshot(string type, ServiceSnapshot snapshot) => new()
    {
        Event = type,
        ServiceName = snapshot.ServiceName,
        Properties = snapshot.Properties.ToDictionary(k => k.Key, v => v.Value),
        Addresses = snapshot.Addresses.ToList(),
        WebhookPort = snapshot.WebhookPort,
        SeenAt = NowIso(),
    };
}
