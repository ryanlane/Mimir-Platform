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

      // Test for v2.1 Channel manifest endpoint
      try {
        const manifest = await api.getChannelsManifest();
        console.log('✅ Channel manifest endpoint detected:', manifest.data);
        this.supportedFeatures.add('channel_manifest');
        this.supportedFeatures.add('v2.1_channels');
        this.supportedFeatures.add('plugin_system');
        this.apiVersion = '2.1';
      } catch (error) {
        console.log('❌ v2.1 Channel manifest not available, falling back to v1.x');
        this.apiVersion = '1.x';
      }

      // Test for channel health endpoint (sample test)
      try {
        // We'll test with a known channel or handle 404s gracefully
        await api.getChannelHealth('weather_channel');
        this.supportedFeatures.add('channel_health');
      } catch (error) {
        if (error.response?.status === 404) {
          // Channel not found is OK, endpoint exists
          this.supportedFeatures.add('channel_health');
        } else {
          console.log('❌ Channel health endpoint not available');
        }
      }

      // Test for channel testing endpoint
      try {
        await api.testChannel('weather_channel');
        this.supportedFeatures.add('channel_testing');
      } catch (error) {
        if (error.response?.status === 404) {
          // Channel not found is OK, endpoint exists
          this.supportedFeatures.add('channel_testing');
        } else {
          console.log('❌ Channel testing endpoint not available');
        }
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
    return this.apiVersion === '2.1';
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

  // Create feature-aware API wrapper
  createFeatureAwareAPI() {
    const featureAPI = { ...api };

    // Add safe wrappers for v2.1 features
    featureAPI.getChannelsManifestSafe = async () => {
      if (this.hasFeature('channel_manifest')) {
        return api.getChannelsManifest();
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
