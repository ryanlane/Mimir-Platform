# Frontend Implementation Guide: Channel Database Reset Button

## 🎯 **Overview**

Add a "Reset Channels Database" button to your admin interface that clears all channel entries from the database and rebuilds them from the current `channels/` folder contents.

## 🚨 **Important Warnings**

This is a **destructive operation** that:
- ❌ Removes ALL channels from database
- ❌ May break scene assignments if channel IDs changed
- ❌ Cannot be undone
- ✅ Only rebuilds from current filesystem state

## 🛠 **Implementation**

### Basic Button Implementation

```jsx
import React, { useState } from 'react';

function ChannelResetButton() {
  const [isResetting, setIsResetting] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [result, setResult] = useState(null);

  const handleReset = async () => {
    setIsResetting(true);
    try {
      const response = await fetch('/api/admin/channels/reset', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setResult(data);
        // Optionally refresh channel list
        window.location.reload(); // or call your refresh function
      } else {
        throw new Error(data.detail || 'Reset failed');
      }
    } catch (error) {
      console.error('Channel reset failed:', error);
      alert(`Reset failed: ${error.message}`);
    } finally {
      setIsResetting(false);
      setShowConfirm(false);
    }
  };

  return (
    <div className="channel-reset-container">
      {!showConfirm ? (
        <button 
          onClick={() => setShowConfirm(true)}
          className="btn btn-danger"
          disabled={isResetting}
        >
          🔄 Reset Channels Database
        </button>
      ) : (
        <div className="confirm-dialog">
          <h3>⚠️ Confirm Database Reset</h3>
          <p>This will:</p>
          <ul>
            <li>Remove ALL channels from database</li>
            <li>Rebuild from filesystem only</li>
            <li>May break existing scene assignments</li>
            <li>Cannot be undone</li>
          </ul>
          
          <div className="confirm-buttons">
            <button 
              onClick={handleReset}
              disabled={isResetting}
              className="btn btn-danger"
            >
              {isResetting ? '🔄 Resetting...' : '✅ Yes, Reset Database'}
            </button>
            <button 
              onClick={() => setShowConfirm(false)}
              disabled={isResetting}
              className="btn btn-secondary"
            >
              ❌ Cancel
            </button>
          </div>
        </div>
      )}
      
      {result && <ResetResults result={result} />}
    </div>
  );
}
```

### Results Display Component

```jsx
function ResetResults({ result }) {
  const { summary, affected_scenes, warnings } = result;
  
  return (
    <div className="reset-results">
      <h4>✅ Reset Complete</h4>
      
      <div className="summary">
        <h5>📊 Summary</h5>
        <div className="stats">
          <div>Before: {summary.before.total_channels} channels</div>
          <div>After: {summary.after.total_channels} channels</div>
        </div>
        
        <div className="changes">
          {summary.changes.removed_count > 0 && (
            <div className="removed">
              <strong>🗑️ Removed ({summary.changes.removed_count}):</strong>
              <ul>
                {summary.changes.removed_ids.map(id => (
                  <li key={id}>{id}</li>
                ))}
              </ul>
            </div>
          )}
          
          {summary.changes.added_count > 0 && (
            <div className="added">
              <strong>➕ Added ({summary.changes.added_count}):</strong>
              <ul>
                {summary.changes.added_ids.map(id => (
                  <li key={id}>{id}</li>
                ))}
              </ul>
            </div>
          )}
          
          {summary.changes.kept_count > 0 && (
            <div className="kept">
              <strong>✅ Kept ({summary.changes.kept_count}):</strong>
              <ul>
                {summary.changes.kept_ids.map(id => (
                  <li key={id}>{id}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
      
      {affected_scenes.length > 0 && (
        <div className="warnings">
          <h5>⚠️ Affected Scenes</h5>
          <p>These scenes may need channel reassignment:</p>
          <ul>
            {affected_scenes.map(scene => (
              <li key={scene.scene_id}>
                Scene "{scene.scene_name}" was using channel "{scene.channel_id}"
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

### Advanced Implementation with Pre-Check

```jsx
function AdvancedChannelResetButton() {
  const [orphanedChannels, setOrphanedChannels] = useState(null);
  const [loading, setLoading] = useState(false);

  const checkOrphanedChannels = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/admin/channels/orphaned');
      const data = await response.json();
      setOrphanedChannels(data);
    } catch (error) {
      console.error('Failed to check orphaned channels:', error);
    } finally {
      setLoading(false);
    }
  };

  const performReset = async () => {
    // ... same reset logic as above
  };

  return (
    <div className="advanced-reset">
      <div className="pre-check">
        <button 
          onClick={checkOrphanedChannels}
          disabled={loading}
          className="btn btn-info"
        >
          🔍 Check Orphaned Channels
        </button>
        
        {orphanedChannels && (
          <div className="orphaned-report">
            <h4>📋 Current State</h4>
            <p>
              Database: {orphanedChannels.total_db_channels} channels<br/>
              Filesystem: {orphanedChannels.total_filesystem_channels} channels<br/>
              Orphaned: {orphanedChannels.count} channels
            </p>
            
            {orphanedChannels.count > 0 && (
              <div className="orphaned-list">
                <h5>🗑️ Will be removed:</h5>
                <ul>
                  {orphanedChannels.orphaned_channels.map(ch => (
                    <li key={ch.id}>
                      {ch.id} ({ch.name}) - {ch.scenes_using} scenes using
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            <button 
              onClick={performReset}
              className="btn btn-danger"
              disabled={loading}
            >
              🔄 Proceed with Reset
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

## 🎨 **CSS Styling Examples**

```css
.channel-reset-container {
  padding: 20px;
  border: 2px solid #ff6b6b;
  border-radius: 8px;
  background: #fff5f5;
  margin: 20px 0;
}

.confirm-dialog {
  text-align: center;
  padding: 20px;
}

.confirm-dialog h3 {
  color: #d63031;
  margin-bottom: 15px;
}

.confirm-dialog ul {
  text-align: left;
  margin: 15px 0;
  padding-left: 20px;
}

.confirm-buttons {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 20px;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-weight: bold;
}

.btn-danger {
  background: #d63031;
  color: white;
}

.btn-secondary {
  background: #636e72;
  color: white;
}

.btn-info {
  background: #0984e3;
  color: white;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.reset-results {
  margin-top: 20px;
  padding: 15px;
  background: #d1f2eb;
  border-radius: 5px;
}

.changes div {
  margin: 10px 0;
}

.removed { color: #d63031; }
.added { color: #00b894; }
.kept { color: #0984e3; }

.warnings {
  margin-top: 15px;
  padding: 10px;
  background: #fff3cd;
  border-radius: 5px;
}
```

## 🚀 **Integration Tips**

### 1. **Add to Admin Dashboard**
Place this button in a dedicated "System Administration" or "Channel Management" section.

### 2. **Permission Check**
```jsx
// Only show to admin users
{user.role === 'admin' && <ChannelResetButton />}
```

### 3. **Confirmation Steps**
Consider a multi-step confirmation:
1. Check orphaned channels first
2. Show what will be removed/added
3. Require typing "RESET" to confirm
4. Final confirmation dialog

### 4. **Integration with Channel List**
```jsx
function ChannelManagement() {
  const [channels, setChannels] = useState([]);
  
  const refreshChannels = async () => {
    const response = await fetch('/api/channels');
    setChannels(await response.json());
  };
  
  const handleResetComplete = () => {
    refreshChannels(); // Refresh the channel list
  };
  
  return (
    <div>
      <ChannelList channels={channels} />
      <ChannelResetButton onComplete={handleResetComplete} />
    </div>
  );
}
```

## 📋 **User Experience Recommendations**

1. **Clear Warning**: Make it obvious this is destructive
2. **Show Impact**: Display what will be removed/added before reset
3. **Progress Indicator**: Show loading state during reset
4. **Success Feedback**: Display detailed results after reset
5. **Auto Refresh**: Refresh relevant UI components after reset
6. **Error Handling**: Show clear error messages if reset fails

## 🔗 **Related Endpoints**

Before implementing the reset button, you might want to also implement:
- `GET /api/admin/channels/orphaned` - Check what will be cleaned up
- `POST /api/admin/reload-channels` - Gentler alternative that doesn't delete
- `DELETE /api/admin/channels/{id}` - Remove specific channels

This gives users more granular control before using the nuclear "reset" option!

## 📞 **API Endpoint Reference**

**Endpoint:** `POST /api/admin/channels/reset`  
**Method:** POST  
**Body:** None required  
**Response:** Detailed summary of changes and affected scenes  
**Errors:** 500 if database operation fails  

The endpoint is ready to use on your server with the new code changes!
