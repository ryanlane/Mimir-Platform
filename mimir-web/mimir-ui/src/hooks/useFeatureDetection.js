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

// React hook for Mimir Platform API feature detection
import { useState, useEffect } from 'react';
import featureDetection from '../services/featureDetection';

// Hook for feature detection
export const useFeatureDetection = () => {
  const [features, setFeatures] = useState({
    apiVersion: null,
    supportedFeatures: [],
    isLoading: true,
    error: null
  });

  useEffect(() => {
    const detectFeatures = async () => {
      try {
        const result = await featureDetection.detectFeatures();
        setFeatures({
          apiVersion: result.apiVersion,
          supportedFeatures: result.supportedFeatures,
          isLoading: false,
          error: null
        });
      } catch (error) {
        console.error('Feature detection failed:', error);
        // Don't let feature detection errors break the app
        // Default to basic functionality
        setFeatures({
          apiVersion: '2.3', // Assume modern API if detection fails
          supportedFeatures: ['display_management', 'v2.3_displays'], // Basic display features
          isLoading: false,
          error: error.message
        });
      }
    };

    detectFeatures();
  }, []);

  return {
    ...features,
    hasFeature: (featureName) => featureDetection.hasFeature(featureName),
    supportsV21: () => featureDetection.supportsV21(),
    supportsV23: () => featureDetection.supportsV23(),
    supportsPluginSystem: () => featureDetection.supportsPluginSystem(),
    supportsChannelHealth: () => featureDetection.supportsChannelHealth(),
    supportsChannelTesting: () => featureDetection.supportsChannelTesting(),
    supportsEnhancedWebSocket: () => featureDetection.supportsEnhancedWebSocket(),
    supportsDisplayManagement: () => featureDetection.supportsDisplayManagement(),
    getFeatureAwareAPI: () => featureDetection.createFeatureAwareAPI()
  };
};

// Hook for conditional feature rendering
export const useFeatureFlag = (featureName) => {
  const { hasFeature, isLoading } = useFeatureDetection();
  return {
    isEnabled: hasFeature(featureName),
    isLoading
  };
};

// Hook for v2.1 features specifically
export const useV21Features = () => {
  const { supportsV21, isLoading, apiVersion } = useFeatureDetection();
  return {
    isV21: supportsV21(),
    isLoading,
    apiVersion
  };
};
