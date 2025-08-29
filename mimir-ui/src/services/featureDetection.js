// Feature detection service for Mimir Platform API v2.1
import { api } from './api';

class FeatureDetectionService {
  constructor() {
    this.apiVersion = null;
    this.supportedFeatures = new Set();
    this.detectionPromise = null;
    this.lastDetectionTime = null;
    this.cacheTimeout = 5 * 60 * 1000; // 5 minutes cache
  }

  // Main feature detection method with caching
  async detectFeatures() {
    // Return cached results if still valid
    if (this.detectionPromise && this.lastDetectionTime && 
        (Date.now() - this.lastDetectionTime) < this.cacheTimeout) {
      console.log('🔄 Using cached feature detection results');
      return this.detectionPromise;
    }

    // Clear old cache
    if (this.detectionPromise) {
      console.log('🧹 Clearing expired feature detection cache');
    }

    this.detectionPromise = this._performDetection();
    return this.detectionPromise;
  }

  async _performDetection() {
    try {
      console.log('🔍 Detecting Mimir Platform API capabilities...');
      
      // Test for v2.1 WebSocket status endpoint
      try {
        const wsStatus = await api.getWebSocketStatus();
        console.log('✅ WebSocket status endpoint detected:', wsStatus.data);
        this.supportedFeatures.add('websocket_status');
        this.supportedFeatures.add('v2.1_websocket');
      } catch (error) {
        console.log('❌ v2.1 WebSocket status not available');
      }

      // Test for v2.3 Display management endpoints
      try {
        await api.getDisplays();
        console.log('✅ Display management endpoints detected');
        this.supportedFeatures.add('display_management');
        this.supportedFeatures.add('v2.3_displays');
        this.apiVersion = '2.3';
      } catch (error) {
        console.log('❌ v2.3 Display management not available');
      }

      // Test for embedded plugin system by checking available channels
      try {
        const channels = await api.getChannels();
        console.log('✅ Embedded plugin system detected:', channels.data);
        this.supportedFeatures.add('embedded_plugins');
        this.supportedFeatures.add('v2.1_channels');
        this.supportedFeatures.add('plugin_system');
        this.apiVersion = '2.1';
        
        // If we have channels, test manifest endpoint for working channels only
        if (channels.data?.channels?.length > 0) {
          let manifestFound = false;
          for (const channel of channels.data.channels) {
            try {
              await api.getChannelManifest(channel.id);
              console.log('✅ Channel manifest endpoint detected for:', channel.id);
              this.supportedFeatures.add('channel_manifest');
              manifestFound = true;
              break; // Stop after finding one working manifest
            } catch (manifestError) {
              console.log(`⚠️ Channel manifest not available for ${channel.id}:`, manifestError.response?.data?.detail || manifestError.message);
              // Continue to next channel
            }
          }
          if (!manifestFound) {
            console.log('❌ No working channel manifests found');
          }
        }
      } catch (error) {
        console.log('❌ Embedded plugin system not available, falling back to v1.x');
        this.apiVersion = '1.x';
      }

      // Test for channel health endpoint with actual available channels
      try {
        const channels = await api.getChannels();
        if (channels.data?.channels?.length > 0) {
          // Try the photoframe channel first since we know it works
          const workingChannel = channels.data.channels.find(ch => ch.id === 'com.epaperframe.photoframe') 
                               || channels.data.channels[0];
          try {
            await api.getChannelHealth(workingChannel.id);
            console.log('✅ Channel health endpoint detected for:', workingChannel.id);
            this.supportedFeatures.add('channel_health');
          } catch (healthError) {
            if (healthError.response?.status === 404) {
              // Channel not found is OK, endpoint exists
              this.supportedFeatures.add('channel_health');
              console.log('✅ Channel health endpoint exists (404 response is expected)');
            } else {
              console.log('❌ Channel health endpoint not available:', healthError.message);
            }
          }
        } else {
          console.log('❌ No channels available to test health endpoint');
        }
      } catch (error) {
        console.log('❌ Cannot test channel health - channels endpoint failed:', error.message);
      }

      // Test for channel testing endpoint with actual available channels  
      try {
        const channels = await api.getChannels();
        if (channels.data?.channels?.length > 0) {
          // Try the photoframe channel first since we know it works
          const workingChannel = channels.data.channels.find(ch => ch.id === 'com.epaperframe.photoframe') 
                               || channels.data.channels[0];
          try {
            await api.testChannel(workingChannel.id);
            console.log('✅ Channel testing endpoint detected for:', workingChannel.id);
            this.supportedFeatures.add('channel_testing');
          } catch (testError) {
            if (testError.response?.status === 404) {
              // Channel not found is OK, endpoint exists
              this.supportedFeatures.add('channel_testing');
              console.log('✅ Channel testing endpoint exists (404 response is expected)');
            } else {
              console.log('❌ Channel testing endpoint not available:', testError.message);
            }
          }
        } else {
          console.log('❌ No channels available to test testing endpoint');
        }
      } catch (error) {
        console.log('❌ Cannot test channel testing - channels endpoint failed:', error.message);
      }

      console.log('🎯 Feature detection complete:', {
        apiVersion: this.apiVersion,
        supportedFeatures: Array.from(this.supportedFeatures)
      });

      // Mark detection time for caching
      this.lastDetectionTime = Date.now();

      return {
        apiVersion: this.apiVersion,
        supportedFeatures: Array.from(this.supportedFeatures)
      };

    } catch (error) {
      console.error('🚨 Feature detection failed:', error);
      this.apiVersion = '1.x';
      return {
        apiVersion: '1.x',
        supportedFeatures: []
      };
    }
  }

  // Check if a specific feature is supported
  hasFeature(featureName) {
    return this.supportedFeatures.has(featureName);
  }

  // Check API version
  getAPIVersion() {
    return this.apiVersion;
  }

  // Check if v2.1 features are available
  supportsV21() {
    return this.apiVersion === '2.1' || this.apiVersion === '2.3';
  }

  // Check if v2.3 features are available
  supportsV23() {
    return this.apiVersion === '2.3';
  }

  // Get all supported features
  getSupportedFeatures() {
    return Array.from(this.supportedFeatures);
  }

  // Feature-specific checks
  supportsPluginSystem() {
    return this.hasFeature('plugin_system');
  }

  supportsChannelHealth() {
    return this.hasFeature('channel_health');
  }

  supportsChannelTesting() {
    return this.hasFeature('channel_testing');
  }

  supportsEnhancedWebSocket() {
    return this.hasFeature('v2.1_websocket');
  }

  supportsDisplayManagement() {
    return this.hasFeature('display_management');
  }

  // Create feature-aware API wrapper
  createFeatureAwareAPI() {
    const featureAPI = { ...api };

    // Add safe wrappers for v2.1 features
    featureAPI.getChannelManifestSafe = async (channelId) => {
      if (this.hasFeature('channel_manifest')) {
        return api.getChannelManifest(channelId);
      }
      throw new Error('Channel manifest not supported in this API version');
    };

    featureAPI.testChannelSafe = async (channelId) => {
      if (this.hasFeature('channel_testing')) {
        return api.testChannel(channelId);
      }
      throw new Error('Channel testing not supported in this API version');
    };

    featureAPI.getChannelHealthSafe = async (channelId) => {
      if (this.hasFeature('channel_health')) {
        return api.getChannelHealth(channelId);
      }
      throw new Error('Channel health monitoring not supported in this API version');
    };

    featureAPI.getWebSocketStatusSafe = async () => {
      if (this.hasFeature('websocket_status')) {
        return api.getWebSocketStatus();
      }
      throw new Error('WebSocket status not supported in this API version');
    };

    return featureAPI;
  }

  // Reset detection (for testing or re-detection)
  reset() {
    this.apiVersion = null;
    this.supportedFeatures.clear();
    this.detectionPromise = null;
  }
}

// Create singleton instance
const featureDetection = new FeatureDetectionService();

export default featureDetection;
export { FeatureDetectionService };
