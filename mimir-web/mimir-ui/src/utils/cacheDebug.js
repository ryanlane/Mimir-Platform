// Copyright (C) 2026 Ryan Lane
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published
// by the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

/**
 * Cache Debug Utility
 * Provides debugging interface for API cache
 */

import { api } from '../services/api';

export const CacheDebug = {
  // Show cache stats in console
  showStats() {
    const stats = api.cache.stats();
    console.group('🔍 API Cache Statistics');
    console.log(`📊 Cache Size: ${stats.size} entries`);
    console.log(`💾 Memory Usage: ${(stats.memoryUsage / 1024).toFixed(2)} KB`);
    console.log('📋 Cached Keys:', stats.keys);
    console.groupEnd();
    return stats;
  },

  // Test cache performance
  async testCachePerformance() {
    console.group('⚡ Cache Performance Test');
    
    // Clear cache to start fresh
    api.cache.clear();
    console.log('🗑️ Cache cleared');

    // First request (should be slow - cache miss)
    const start1 = performance.now();
    await api.getChannels();
    const time1 = performance.now() - start1;
    console.log(`📡 First request (cache miss): ${time1.toFixed(2)}ms`);

    // Second request (should be fast - cache hit)
    const start2 = performance.now();
    await api.getChannels();
    const time2 = performance.now() - start2;
    console.log(`⚡ Second request (cache hit): ${time2.toFixed(2)}ms`);

    const speedup = ((time1 - time2) / time1 * 100).toFixed(1);
    console.log(`🚀 Cache speedup: ${speedup}% faster`);

    console.groupEnd();
    
    return { cacheHit: time2, cacheMiss: time1, speedup };
  },

  // Test sub-channel caching
  async testSubChannelCache() {
    console.group('🎨 Sub-Channel Cache Test');
    
    try {
      // Test photo frame sub-channels
      const channelId = 'com.epaperframe.photoframe';
      
      console.log('Testing sub-channel config caching...');
      const start1 = performance.now();
      await api.getSubChannelConfig(channelId);
      const time1 = performance.now() - start1;
      console.log(`First config request: ${time1.toFixed(2)}ms`);

      const start2 = performance.now();
      await api.getSubChannelConfig(channelId);
      const time2 = performance.now() - start2;
      console.log(`Second config request (cached): ${time2.toFixed(2)}ms`);

      console.log('Testing sub-channel list caching...');
      const start3 = performance.now();
      await api.getSubChannels(channelId);
      const time3 = performance.now() - start3;
      console.log(`First list request: ${time3.toFixed(2)}ms`);

      const start4 = performance.now();
      await api.getSubChannels(channelId);
      const time4 = performance.now() - start4;
      console.log(`Second list request (cached): ${time4.toFixed(2)}ms`);

      console.groupEnd();
      return { configCache: time2, listCache: time4 };
    } catch (error) {
      console.error('Sub-channel cache test failed:', error);
      console.groupEnd();
      throw error;
    }
  },

  // Show visual cache indicator
  showVisualIndicator() {
    // Remove existing indicator
    const existing = document.querySelector('.cache-debug-indicator');
    if (existing) existing.remove();

    // Create indicator
    const indicator = document.createElement('div');
    indicator.className = 'cache-debug-indicator';
    indicator.style.cssText = `
      position: fixed;
      top: 10px;
      left: 10px;
      background: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 8px 12px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 12px;
      z-index: 9999;
      max-width: 200px;
      cursor: pointer;
    `;

    const updateStats = () => {
      const stats = api.cache.stats();
      indicator.innerHTML = `
        <div>🔍 Cache: ${stats.size} entries</div>
        <div>💾 ${(stats.memoryUsage / 1024).toFixed(1)} KB</div>
        <div style="font-size: 10px; margin-top: 4px;">Click to test performance</div>
      `;
    };

    indicator.addEventListener('click', async () => {
      indicator.innerHTML = '⚡ Testing cache...';
      try {
        await this.testCachePerformance();
        updateStats();
      } catch (error) {
        indicator.innerHTML = '❌ Test failed';
        setTimeout(updateStats, 2000);
      }
    });

    updateStats();
    document.body.appendChild(indicator);

    // Update every 5 seconds
    const interval = setInterval(updateStats, 5000);
    
    // Clean up after 60 seconds
    setTimeout(() => {
      clearInterval(interval);
      indicator.remove();
    }, 60000);

    return indicator;
  },

  // Test cache invalidation
  async testCacheInvalidation() {
    console.group('🗑️ Cache Invalidation Test');
    
    try {
      const channelId = 'com.epaperframe.photoframe';
      
      // Load data into cache
      await api.getSubChannels(channelId);
      console.log('✅ Data loaded into cache');
      
      let stats = api.cache.stats();
      console.log(`Cache size before invalidation: ${stats.size}`);
      
      // Simulate a create operation that should invalidate cache
      api.cache.invalidate([`/channels/${channelId}/subchannels`]);
      console.log('🗑️ Cache invalidated');
      
      stats = api.cache.stats();
      console.log(`Cache size after invalidation: ${stats.size}`);
      
      console.groupEnd();
      return true;
    } catch (error) {
      console.error('Cache invalidation test failed:', error);
      console.groupEnd();
      throw error;
    }
  }
};

// Auto-expose to window for browser console debugging
if (typeof window !== 'undefined') {
  window.CacheDebug = CacheDebug;
  console.log('🔍 Cache debugging available via window.CacheDebug');
}

export default CacheDebug;
