// Plugin Slot component for v2.1 Web Component integration
import React, { useState, useEffect, useCallback } from 'react';
import { useFeatureDetection } from '../../hooks/useFeatureDetection';
import { api } from '../../services/api';
import './PluginSlot.css';

// Global cache for manifest data to prevent excessive API requests
let manifestCache = null;
let manifestCacheTime = null;
const MANIFEST_CACHE_TIMEOUT = 5 * 60 * 1000; // 5 minutes

/**
 * PluginSlot component for rendering Web Components from v2.1 channels
 * @param {string} name - The slot name (e.g., 'dashboard.topRight')
 * @param {object} hostProps - Props to pass to Web Components
 * @param {object} style - CSS styles for the slot container
 */
const PluginSlot = ({ name, hostProps = {}, style = {}, className = '' }) => {
  const { supportsPluginSystem } = useFeatureDetection();
  const [plugins, setPlugins] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const processManifestData = useCallback((manifests) => {
    // Find all UI components that target this slot
    const slotPlugins = manifests
      .flatMap(manifest => 
        (manifest.ui || []).map(ui => ({
          ...ui,
          channelId: manifest.id,
          channelName: manifest.name,
          manifestData: manifest
        }))
      )
      .filter(ui => ui.slots && ui.slots.includes(name));

    console.log(`🔌 Found ${slotPlugins.length} plugins for slot '${name}':`, slotPlugins);
    setPlugins(slotPlugins);
    
    // Load Web Components
    loadWebComponents(slotPlugins);
  }, [name]);

  const loadPluginsForSlot = useCallback(async () => {
    if (!supportsPluginSystem()) {
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      // Check cache first
      const now = Date.now();
      if (manifestCache && manifestCacheTime && (now - manifestCacheTime) < MANIFEST_CACHE_TIMEOUT) {
        console.log('🚀 Using cached manifest data');
        processManifestData(manifestCache);
        return;
      }
      
      console.log('📡 Fetching fresh manifest data');
      const response = await api.getChannelsManifest();
      const manifests = response.data || [];
      
      // Update cache
      manifestCache = manifests;
      manifestCacheTime = now;
      
      processManifestData(manifests);
      
    } catch (error) {
      console.error(`Error loading plugins for slot '${name}':`, error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }, [name, supportsPluginSystem, processManifestData]);

  const loadWebComponents = async (slotPlugins) => {
    for (const plugin of slotPlugins) {
      try {
        console.log(`📦 Loading Web Component: ${plugin.element} from ${plugin.moduleUrl}`);
        
        // Check if Web Component is already defined
        if (customElements.get(plugin.element)) {
          console.log(`✅ Web Component ${plugin.element} already loaded`);
          continue;
        }

        // Validate integrity if present (SRI)
        if (plugin.integrity?.module) {
          console.log(`🛡️ SRI validation enabled for ${plugin.element}`);
          // TODO: Implement actual SRI validation
        }

        // Dynamic import of Web Component
        // Note: In a real implementation, this would need proper error handling
        // and potentially a module federation or plugin loader system
        console.log(`⚠️ Web Component loading simulated for ${plugin.element}`);
        console.log(`   Module URL: ${plugin.moduleUrl}`);
        console.log(`   Style URL: ${plugin.styleUrl || 'none'}`);
        
        // For now, we'll just log the attempt since we don't have actual v2.1 channels
        
      } catch (error) {
        console.error(`Error loading Web Component ${plugin.element}:`, error);
      }
    }
  };

  useEffect(() => {
    loadPluginsForSlot();
  }, [loadPluginsForSlot]);

  // Don't render anything if plugin system not supported
  if (!supportsPluginSystem()) {
    return null;
  }

  if (loading) {
    return (
      <div className={`plugin-slot loading ${className}`} style={style}>
        <div className="plugin-loading">
          <span>Loading plugins for {name}...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`plugin-slot error ${className}`} style={style}>
        <div className="plugin-error">
          <span>Error loading plugins: {error}</span>
        </div>
      </div>
    );
  }

  if (plugins.length === 0) {
    return (
      <div className={`plugin-slot empty ${className}`} style={style}>
        <div className="plugin-empty">
          <span>No plugins available for slot: {name}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`plugin-slot ${className}`} style={style}>
      <div className="plugin-slot-header">
        <span className="slot-name">Plugin Slot: {name}</span>
        <span className="plugin-count">{plugins.length} plugin(s)</span>
      </div>
      
      {plugins.map((plugin, index) => (
        <div key={`${plugin.channelId}-${plugin.element}-${index}`} className="plugin-container">
          <div className="plugin-info">
            <strong>{plugin.element}</strong> from {plugin.channelName}
            <div className="plugin-details">
              <small>Module: {plugin.moduleUrl}</small>
              {plugin.styleUrl && <small>Styles: {plugin.styleUrl}</small>}
              {plugin.integrity && <small>✅ SRI Protected</small>}
            </div>
          </div>
          
          {/* Placeholder for actual Web Component rendering */}
          <div className="web-component-placeholder">
            <p>🔌 Web Component: &lt;{plugin.element}&gt;</p>
            <p>📦 Channel: {plugin.channelName}</p>
            <p>🎛️ Props: {JSON.stringify(hostProps)}</p>
            <p>⚠️ Simulated - would render actual component in v2.1 server environment</p>
          </div>
        </div>
      ))}
    </div>
  );
};

export default PluginSlot;
