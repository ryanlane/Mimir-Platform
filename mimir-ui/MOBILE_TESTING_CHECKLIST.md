# Mobile Testing Checklist for Mimir UI

## ✅ After Deployment - Test These Areas:

### 1. **Scenes Page**
- [ ] Scenes list loads correctly
- [ ] Scene thumbnails/images display properly
- [ ] "Display Now" button works
- [ ] Create/Edit scene functionality
- [ ] Real-time updates via WebSocket

### 2. **Dashboard**
- [ ] Activity log updates in real-time
- [ ] Current scene display status
- [ ] Scene cards and thumbnails
- [ ] WebSocket connection status

### 3. **Channels Page**
- [ ] Channel list loads
- [ ] Channel settings can be opened
- [ ] Channel configuration works
- [ ] Image uploads (if applicable)

### 4. **Displays Page**
- [ ] Display list loads correctly
- [ ] Display images render properly
- [ ] Scene assignment works
- [ ] Display registration

### 5. **Settings Page**
- [ ] Connection configuration section visible
- [ ] Can test API and WebSocket connections
- [ ] Mobile Connection Guide expands/collapses
- [ ] Current URL detection is accurate

## 🔧 **Connection Testing**

### Open iOS Safari DevTools (via Mac Safari):
1. Open Safari on Mac
2. Safari > Preferences > Advanced > Show Develop menu
3. Connect iPhone to Mac via USB
4. Develop > [Your iPhone] > [Mimir UI Tab]

### Console Commands to Test:
```javascript
// Check device info
console.log(window.mimirDebug);

// Test API connection
window.mimirDebug.testConnection();

// Check current URLs
console.log('API Base URL:', window.location.origin + ':5000/api');
console.log('WebSocket URL:', window.location.protocol.replace('http', 'ws') + '//' + window.location.hostname + ':5000');

// Test WebSocket connection
const testWs = new WebSocket('ws://' + window.location.hostname + ':5000/ws');
testWs.onopen = () => console.log('✅ WebSocket connected');
testWs.onerror = (e) => console.error('❌ WebSocket failed:', e);
```

## 🐛 **Troubleshooting Steps**

### If scenes still don't load:
1. Check browser console for errors
2. Go to Settings > Connection Configuration
3. Try manual configuration with your server's IP:
   - API: `http://[YOUR_SERVER_IP]:5000`
   - WebSocket: `ws://[YOUR_SERVER_IP]:5000`
4. Test the connections using the Test buttons

### If connection issues persist:
1. Ensure mobile device is on same WiFi network
2. Check if router/firewall blocks port 5000
3. Try accessing `http://[YOUR_SERVER_IP]:5000/health` directly in mobile browser
4. Disable VPN/proxy on mobile device
5. Try different mobile browser (Chrome vs Safari)

## 📱 **iOS Safari Specific**

### Common iOS Safari Issues:
- Strict cookie policies
- WebSocket connection limitations
- Cache-related problems

### Solutions:
- Clear Safari cache and website data
- Disable "Block All Cookies" in Settings > Safari
- Try Private Browsing mode
- Consider using Chrome or Firefox on iOS

## 🎯 **Success Indicators**

When everything is working correctly, you should see:
- ✅ Scenes load with thumbnails on mobile
- ✅ Real-time updates when scenes change
- ✅ WebSocket status shows "Connected"
- ✅ No console errors related to network requests
- ✅ All sections (Dashboard, Scenes, Channels, Displays) load properly

## 🔄 **Quick Mobile Test**

1. Open mimir-ui on mobile
2. Check console (if possible) for any errors
3. Navigate to Scenes - should load properly
4. Navigate to Dashboard - activity should be visible
5. Navigate to Settings - Connection Guide should help with any issues

If any section still has issues, use the Connection Configuration in Settings to manually set the correct URLs for your environment.
