# Distribution Monitoring in Mimir API

**Distribution monitoring** is a real-time performance monitoring system that tracks how content is distributed across multiple display devices in your Mimir platform. Here's how it works:

## 🎯 **What is Distribution Monitoring?**

Distribution monitoring tracks the health and performance of your multi-display content distribution system, which operates in three modes:

1. **MIRROR** - All displays show the same content (default)
2. **SEQUENTIAL** - Displays cycle through content in order using a queue
3. **RANDOM_UNIQUE** - Displays get randomized content without duplication using a shuffle bag

## 🔧 **How It Works**

### **1. Background Monitoring Task**
Located in your `main.py` at line 39, the system starts a background monitoring task when `distribution_enabled` is `True`:

```python
if settings.distribution_enabled:
    import asyncio
    asyncio.create_task(distribution_service.start_distribution_monitoring())
    logger.info("Distribution monitoring started")
```

### **2. Monitoring Loop**
The monitoring system runs every **30 seconds** and:

- **Queries active scenes** from the database
- **Collects performance metrics** from Redis:
  - Active content leases (displays currently showing content)
  - Queue sizes (remaining content in sequential/random queues)
  - Assignment rates (content assignments per minute)
  - Average assignment times
  - Memory usage statistics
  - Last activity timestamps

### **3. Real-time Broadcasting**
Performance data is broadcast via **WebSocket** to connected dashboard clients:

```python
await manager.broadcast_distribution_performance(
    scene_id=scene.id,
    performance_metrics=performance_metrics
)
```

## 📊 **What Gets Monitored**

The system tracks these key metrics for each scene:

```python
performance_metrics = {
    "active_leases": status.get("active_leases", 0),           # Displays currently showing content
    "queue_size": status.get("queue_status", {}).get("total_items", 0),  # Remaining content in queue
    "assignments_last_minute": status.get("metrics", {}).get("assignments_last_minute", 0),  # Assignment rate
    "average_assignment_time": status.get("metrics", {}).get("avg_assignment_time", 0),      # Performance timing
    "memory_usage": status.get("memory_usage", {}),           # Redis memory usage
    "last_activity": status.get("last_activity")              # When last content was assigned
}
```

## 🌐 **Frontend Integration**

The monitoring data is consumed by:

1. **Distribution Monitor Component** (`DistributionMonitor.js`) - Shows live metrics and events
2. **Dashboard HTML** (`distribution_dashboard.html`) - Administrative monitoring interface

These frontends display:
- Real-time performance charts
- Event logs (content assignments, queue updates, etc.)
- System health indicators
- Redis connection status

## ⚡ **Redis Dependency**

Distribution monitoring **requires Redis** to function because:
- Content distribution queues are stored in Redis
- Performance metrics are calculated from Redis data structures
- Redis provides the high-speed operations needed for multi-display coordination

When Redis is unavailable, the monitoring gracefully degrades and reports `"redis_unavailable"` status.

## 🎛️ **Configuration**

The monitoring is controlled by these settings:
- `distribution_enabled` - Enables/disables the entire distribution system
- `redis_enabled` - Required for distribution features
- The monitoring loop runs every 30 seconds (hardcoded)

## 🔍 **Monitoring Events**

The system broadcasts various WebSocket events that can be monitored:

### Performance Events
- `distribution_performance` - Overall system performance metrics (every 30 seconds)
- `queue_status` - Queue state changes and updates

### Content Events
- `content_assigned` - When content is assigned to a display
- `content_released` - When a display finishes showing content
- `lease_renewed` - When content lease is extended

### Queue Events
- `epoch_started` - When a new content distribution cycle begins
- `queue_updated` - When queue contents change

## 📈 **Performance Metrics**

Key performance indicators tracked include:

| Metric | Description | Purpose |
|--------|-------------|---------|
| **Active Leases** | Number of displays currently showing content | System utilization |
| **Queue Size** | Remaining items in distribution queue | Content backlog |
| **Assignment Rate** | Content assignments per minute | Throughput monitoring |
| **Assignment Time** | Average time to assign content | Performance optimization |
| **Memory Usage** | Redis memory consumption | Resource monitoring |
| **Last Activity** | Timestamp of last content assignment | System activity |

## 🛠️ **Implementation Details**

### Service Architecture
The distribution monitoring is implemented across several components:

1. **`DistributionService`** (`app/services/distribution.py`) - Core monitoring logic
2. **`WebSocketService`** (`app/services/websocket.py`) - Real-time broadcasting
3. **Background Task** (`main.py`) - Periodic monitoring execution

### Monitoring Flow
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Background    │    │  Distribution    │    │   WebSocket     │
│   Monitoring    ├────┤     Service      ├────┤   Broadcasting  │
│   (30s cycle)   │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│     Redis       │    │    Database      │    │   Dashboard     │
│   (Metrics)     │    │   (Scenes)       │    │   Clients       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

This system provides essential observability for managing content across multiple displays, ensuring you can monitor performance, detect issues, and optimize content delivery in real-time.