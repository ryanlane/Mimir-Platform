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
        setFeatures({
          apiVersion: '1.x',
          supportedFeatures: [],
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
    supportsPluginSystem: () => featureDetection.supportsPluginSystem(),
    supportsChannelHealth: () => featureDetection.supportsChannelHealth(),
    supportsChannelTesting: () => featureDetection.supportsChannelTesting(),
    supportsEnhancedWebSocket: () => featureDetection.supportsEnhancedWebSocket(),
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
