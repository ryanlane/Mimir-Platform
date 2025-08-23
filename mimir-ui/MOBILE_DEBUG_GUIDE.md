# Mobile iOS Safari Debugging Guide

## 🚨 Issue: Channels and Displays sections not showing items on iOS Safari

**Current Status:**
- ✅ Scenes page: Working correctly  
- ❌ Channels page: Not showing channels
- ❌ Displays page: Not showing displays

## 🔧 **NEW: Debug Panel Added**

I've just added a **Debug Panel** to the Channels and Displays pages that will help us diagnose the exact issue.

### How to Use the Debug Panel:

1. **Navigate to Channels or Displays page** on iOS Safari
2. **Look for a "Debug" button** in the bottom-right corner
3. **Tap "Debug"** to open the debug panel
4. **Tap "Run Tests"** to diagnose connection issues
5. **Check the results** for any failures

### What the Debug Panel Tests:

- ✅ **API Base URL** - Verifies correct URL detection
- ✅ **Health Endpoint** - Tests if server is accessible
- ✅ **Channels Endpoint** - Tests /api/channels response
- ✅ **Displays Endpoint** - Tests /api/displays response  
- ✅ **Scenes Endpoint** - Tests /api/scenes response (for comparison)
- ✅ **Network Info** - Shows current connection details

## 📱 **Testing Steps After Deployment**

### Step 1: Deploy the New Version
```bash
npm run rsync  # (or your deployment method)
```

### Step 2: Test on iOS Safari
1. **Clear Safari cache** (Settings > Safari > Clear History and Website Data)
2. **Open mimir-ui** on iOS Safari
3. **Navigate to Channels page**
4. **Tap the "Debug" button** (bottom-right corner)
5. **Tap "Run Tests"**
6. **Screenshot the results** and share them

### Step 3: Check Console (if possible)
If you can connect iOS Safari to Mac Safari:
1. **Connect iPhone to Mac** via USB
2. **Mac Safari > Develop > [Your iPhone] > [Mimir UI Tab]**
3. **Check Console tab** for error messages
4. **Look for network errors**, CORS issues, or API failures

## 🔍 **Expected Debug Results**

### ✅ **If Everything Works** (should show):
```
✓ apiBaseUrl: API Base URL: http://[your-server]:5000/api
✓ health: Health endpoint accessible  
✓ channels: Channels loaded: X channels
✓ displays: Displays loaded: X displays
✓ scenes: Scenes loaded: X scenes
```

### ❌ **Common Failure Patterns:**

**Pattern 1: Network/CORS Issues**
```
✗ health: Health endpoint error: Failed to fetch
✗ channels: Channels error: NetworkError
```
→ **Solution**: Server not accessible from mobile network

**Pattern 2: Empty API Responses**
```
✓ health: Health endpoint accessible
✓ channels: Channels loaded: 0 channels  
✓ displays: Displays loaded: 0 displays
```
→ **Solution**: API accessible but no data configured

**Pattern 3: API Version Issues**
```
✓ health: Health endpoint accessible
✗ channels: Channels error: 404 Not Found
✗ displays: Displays error: 404 Not Found  
```
→ **Solution**: API doesn't support these endpoints

## 🛠️ **Troubleshooting Actions**

### If Network/Connection Fails:
1. **Verify WiFi** - Ensure iPhone on same network as server
2. **Test direct access** - Try `http://[server-ip]:5000/health` in Safari
3. **Check firewall** - Server might block mobile connections
4. **Try manual config** - Use Settings > Connection Configuration

### If API Returns Empty Data:
1. **Check server logs** - Are channels/displays configured?
2. **Test on desktop** - Do Channels/Displays work on desktop browser?
3. **Verify API version** - Might need newer API version

### If Console Shows Errors:
1. **CORS errors** - Server needs mobile domain in CORS config
2. **Certificate errors** - HTTPS/SSL issues on mobile
3. **JavaScript errors** - Code compatibility issues

## 📊 **Quick Network Test**

Before using the Debug Panel, test basic connectivity:

```javascript
// Paste in Safari DevTools Console (if available):
fetch(window.location.origin + ':5000/health')
  .then(r => r.json())
  .then(d => console.log('✅ Server accessible:', d))
  .catch(e => console.error('❌ Server failed:', e))
```

## 🎯 **Action Plan**

1. **Deploy updated app** with Debug Panel
2. **Test Debug Panel** on iOS Safari
3. **Share debug results** - Screenshot or copy the test results  
4. **Based on results**, we'll either:
   - Fix network/CORS configuration
   - Address API data issues  
   - Resolve mobile-specific JavaScript problems

The Debug Panel will give us the exact diagnosis we need to fix the Channels and Displays loading issue! 🎉
