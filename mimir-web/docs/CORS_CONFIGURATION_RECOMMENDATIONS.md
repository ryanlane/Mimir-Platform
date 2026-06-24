# CORS Configuration Recommendations for Mimir Platform API

**Date:** August 22, 2025  
**Priority:** High 🚨  
**Context:** Frontend Web Component integration and API access issues  

---

## 🎯 **Executive Summary**

The current CORS configuration is blocking Web Component functionality and causing authentication failures. The primary issue is using wildcard origins (`*`) with credentials, which violates browser security policies.

**Impact:**
- ❌ Web Component management interfaces fail to load data
- ❌ Channel configuration APIs return CORS errors
- ❌ File upload functionality blocked
- ❌ Poor developer experience requiring workarounds

---

## 🔴 **Current Problem**

### **Error Encountered:**
```
Access-Control-Allow-Origin header must not be wildcard '*' when request's credentials mode is 'include'
```

### **Root Cause:**
```javascript
// Current problematic setup:
Access-Control-Allow-Origin: *
Access-Control-Allow-Credentials: true  // ❌ This combination is invalid
```

Browser security policy prevents wildcard CORS origins when credentials are included in requests.

---

## ✅ **Recommended Solution**

### **1. Use Explicit Origins Instead of Wildcards**

```javascript
// ❌ Current (broken)
Access-Control-Allow-Origin: *
Access-Control-Allow-Credentials: true

// ✅ Recommended (working)
Access-Control-Allow-Origin: http://localhost:3000, http://mimir.local:3000
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With
Access-Control-Max-Age: 86400
```

### **2. Environment-Based Configuration**

```bash
# Development
CORS_ORIGINS=http://localhost:3000,http://mimir.local:3000,http://127.0.0.1:3000

# Production  
CORS_ORIGINS=https://your-mimir-frontend.com,https://admin.mimir-platform.com

# Local network (for testing)
CORS_ORIGINS=http://mimir.local:3000,http://192.168.1.*:3000
```

---

## 🛠 **Implementation Options**

### **Option A: Unified Explicit Origins (Recommended)**
Apply explicit origins to all endpoints for consistency:

```javascript
// All /api/* endpoints
Access-Control-Allow-Origin: specific-domains-only
Access-Control-Allow-Credentials: true
```

**Pros:**
- ✅ Consistent behavior across all endpoints
- ✅ Supports authenticated requests everywhere
- ✅ Future-proof for new features

### **Option B: Differentiated by Endpoint Type**
Different CORS policies based on authentication needs:

```javascript
// Public read-only endpoints
GET /api/channels/manifest
Access-Control-Allow-Origin: * (no credentials)

// Authenticated endpoints  
POST /api/channels/{id}/upload
PUT /api/channels/{id}/settings
Access-Control-Allow-Origin: specific-domains + credentials
```

**Pros:**
- ✅ Maximum compatibility for public endpoints
- ⚠️ More complex to maintain

---

## 💻 **Express.js Implementation**

If using Express with the `cors` middleware:

```javascript
const cors = require('cors');

const corsOptions = {
  origin: process.env.CORS_ORIGINS?.split(',') || [
    'http://localhost:3000',
    'http://mimir.local:3000'
  ],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: [
    'Content-Type', 
    'Authorization', 
    'X-Requested-With'
  ],
  maxAge: 86400 // Cache preflight for 24 hours
};

app.use(cors(corsOptions));
```

### **Alternative: Manual Headers**

```javascript
app.use((req, res, next) => {
  const allowedOrigins = process.env.CORS_ORIGINS?.split(',') || [
    'http://localhost:3000',
    'http://mimir.local:3000'
  ];
  
  const origin = req.headers.origin;
  if (allowedOrigins.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
  }
  
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With');
  res.setHeader('Access-Control-Max-Age', '86400');
  
  if (req.method === 'OPTIONS') {
    res.sendStatus(200);
  } else {
    next();
  }
});
```

---

## 🧪 **Testing the Configuration**

### **Test CORS with curl:**
```bash
# Test preflight request
curl -H "Origin: http://mimir.local:3000" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     http://mimir.local:5000/api/channels/photo-frame/upload

# Expected response should include:
# Access-Control-Allow-Origin: http://mimir.local:3000
# Access-Control-Allow-Credentials: true
```

### **Test from browser console:**
```javascript
// This should work after CORS fix
fetch('http://mimir.local:5000/api/channels/photo-frame/images', {
  credentials: 'include'
})
.then(response => console.log('✅ CORS working:', response.status))
.catch(error => console.error('❌ CORS failed:', error));
```

---

## 🎯 **Critical Endpoints Affected**

These endpoints are currently broken and need immediate CORS fixes:

### **High Priority (Blocking Web Components):**
- `POST /api/channels/{id}/upload` - File uploads
- `GET /api/channels/{id}/images` - Image gallery loading  
- `PUT /api/channels/{id}/settings` - Settings updates
- `DELETE /api/channels/{id}/images/{imageId}` - Image deletion

### **Medium Priority:**
- `GET /api/channels/{id}/hardware` - Hardware status
- `POST /api/channels/{id}/images/{imageId}/toggle` - Image activation
- `PUT /api/channels/{id}/images/{imageId}` - Image metadata updates

---

## 📋 **Action Items for API Team**

### **Immediate (This Week):**
1. ✅ Update CORS configuration to use explicit origins
2. ✅ Deploy to development environment
3. ✅ Test with frontend team

### **Short Term (Next Sprint):**
1. ✅ Configure environment-specific CORS origins
2. ✅ Update production deployment
3. ✅ Document CORS configuration for future reference

### **Testing Checklist:**
- [ ] Web Component image gallery loads without errors
- [ ] File uploads work from management interface  
- [ ] Settings can be saved through Web Components
- [ ] No CORS errors in browser console
- [ ] All environments (dev/staging/prod) working

---

## 🔒 **Security Considerations**

### **✅ Recommended Practices:**
- Use explicit origins instead of wildcards
- Validate origins against a whitelist
- Use environment variables for origin configuration
- Monitor CORS logs for unauthorized access attempts

### **⚠️ Avoid These:**
- Never use `Access-Control-Allow-Origin: *` with credentials
- Don't include sensitive domains in development CORS lists
- Avoid overly permissive header allowlists

---

## 📞 **Frontend Team Contact**

If you need to test the CORS changes or have questions about the frontend requirements:

**Frontend Endpoints Used:**
- Development: `http://localhost:3000`, `http://mimir.local:3000`
- Web Components: Load from `{server}/api/channels/{id}/ui/component.js`
- API Calls: `{server}/api/channels/{id}/*`

**Testing Support:**
- We can provide browser console tests
- Web Component integration testing available
- Real-time verification during deployment

---

## 🎉 **Expected Benefits**

After implementing these CORS fixes:

### **✅ User Experience:**
- Photo frame management interface works properly
- File uploads function without errors  
- Real-time settings updates
- Seamless Web Component integration

### **✅ Developer Experience:**  
- No more CORS workarounds needed
- Clean browser console (no CORS errors)
- Faster development iteration
- Better debugging capabilities

### **✅ Platform Benefits:**
- Full Web Component functionality
- Better channel management
- Enhanced user interfaces
- Future-ready for new features

---

## 📅 **Timeline**

**Immediate Impact:** This is blocking Web Component functionality and should be prioritized as a **critical bug fix**.

**Implementation Time:** ~1-2 hours for configuration changes  
**Testing Time:** ~30 minutes with frontend team  
**Deployment:** Can be deployed independently of other features  

---

**Contact for Questions:**  
Frontend Development Team  
**Priority:** Critical - Blocking user-facing features
