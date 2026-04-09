import { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import { normalizeScene, buildPayload, evaluatePushSelectable as evalPushSelectable, validateForm } from './sceneFormUtils';

/**
 * useSceneFormLogic
 * Centralizes state + side-effects for SceneForm.
 * Responsibilities:
 *  - Manage formData
 *  - Load channel manifests (subchannels + push capabilities)
 *  - Handle schedule CRUD
 *  - Provide validation + submit save function
 */
export function useSceneFormLogic({ scene, channels, onClose }) {
  const [formData, setFormData] = useState(normalizeScene(scene));
  const [validationErrors, setValidationErrors] = useState([]);
  const [loading, setLoading] = useState(false);

  // Subchannel / capability state
  const [subChannelSupport, setSubChannelSupport] = useState({});
  const [subChannelRequirements, setSubChannelRequirements] = useState({});
  const [availableSubChannels, setAvailableSubChannels] = useState({});
  const [channelPushCapabilities, setChannelPushCapabilities] = useState({});
  const [loadingSubChannels, setLoadingSubChannels] = useState(false);
  const [pushSelectable, setPushSelectable] = useState(false);
  const [capabilitiesLoaded, setCapabilitiesLoaded] = useState(false);
  const [pushSelectableReason, setPushSelectableReason] = useState('Select a channel');

  // Schedule state
  const [scheduleData, setScheduleData] = useState({ freq_unit: 'hour', freq_value: 1, enabled: true });
  const [currentSchedule, setCurrentSchedule] = useState(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [scheduleModified, setScheduleModified] = useState(false);

  const evaluatePushSelectable = useCallback((assignments, caps, loaded) => {
    // If nothing selected
    if (!assignments || assignments.length === 0) {
      setPushSelectable(false);
      setPushSelectableReason('Select a channel');
      if (loaded && formData.update_strategy === 'push') {
        setFormData(prev => ({ ...prev, update_strategy: 'scheduler' }));
      }
      return;
    }
    // If capabilities still loading
    const allHaveCaps = assignments.every(a => caps[a.channel_id] !== undefined);
    if (!loaded || !allHaveCaps) {
      setPushSelectable(false);
      setPushSelectableReason('Loading channel capabilities...');
      return; // do not auto-downgrade until we know
    }
    const selectable = evalPushSelectable(assignments, caps);
    setPushSelectable(selectable);
    if (!selectable) {
      setPushSelectableReason('Selected channel does not support real-time push');
      if (formData.update_strategy === 'push') {
        setFormData(prev => ({ ...prev, update_strategy: 'scheduler' }));
      }
    } else {
      setPushSelectableReason(null);
    }
  }, [formData.update_strategy]);

  // Schedule CRUD
  const loadSceneSchedule = useCallback(async (sceneId) => {
    if (!sceneId) return;
    try {
      setScheduleLoading(true);
      const resp = await api.getSceneSchedules(sceneId);
      const assignments = resp.data || [];
      if (assignments.length > 0) {
        const jobResp = await api.getSchedulerJob(assignments[0].job_id);
        const schedule = jobResp.data;
        setCurrentSchedule(schedule);
        setScheduleData({ freq_unit: schedule.freq_unit, freq_value: schedule.freq_value, enabled: schedule.enabled });
        setScheduleModified(false);
      } else {
        setCurrentSchedule(null);
        setScheduleData({ freq_unit: 'hour', freq_value: 1, enabled: true });
        setScheduleModified(false);
      }
    } catch (err) {
      setCurrentSchedule(null);
    } finally { setScheduleLoading(false); }
  }, []);

  // When scene changes, normalize initial data and load schedule
  useEffect(() => {
    setFormData(normalizeScene(scene));
    if (scene?.id) loadSceneSchedule(scene.id);
  }, [scene, loadSceneSchedule]);

  const loadCapabilities = useCallback(async () => {
    if (!channels.length) return;
    setLoadingSubChannels(true);
    setCapabilitiesLoaded(false);
    const supportInfo = {}; const requirementsInfo = {}; const subData = {}; const pushCaps = {};
    for (const channel of channels) {
      try {
        const manifestResp = await api.getChannelManifest(channel.id, { forceRefresh: true });
        const manifest = manifestResp.data || {};
        let liveSubchannels = [];
        try {
          const subchannelsResp = await api.getSubChannels(channel.id, { forceRefresh: true });
          liveSubchannels = Array.isArray(subchannelsResp?.data) ? subchannelsResp.data : [];
        } catch (subchannelsError) {
          liveSubchannels = [];
        }
        const hasGalleries = manifest.galleries && Array.isArray(manifest.galleries) && manifest.galleries.length > 0;
        const hasSubchannels = manifest.subchannels && Array.isArray(manifest.subchannels) && manifest.subchannels.length > 0;
        const hasLiveSubchannels = liveSubchannels.length > 0;
        const supportsSubchannels = Boolean(
          hasLiveSubchannels ||
          hasGalleries ||
          hasSubchannels ||
          manifest.capabilities?.supports_gallery ||
          manifest.capabilities?.supports_subchannels ||
          manifest.supports_subchannels
        );
        supportInfo[channel.id] = supportsSubchannels;
        requirementsInfo[channel.id] = { requires_subchannel_selection: false };
        if (hasLiveSubchannels) {
          subData[channel.id] = liveSubchannels.map(sc => ({
            id: sc.id,
            name: sc.name,
            image_count: sc.image_count,
            type: 'subchannel'
          }));
        } else if (hasGalleries) {
          subData[channel.id] = manifest.galleries.map(g => ({ id: g.id, name: g.name, image_count: g.image_count, type: 'gallery' }));
        } else if (hasSubchannels) {
          subData[channel.id] = manifest.subchannels.map(sc => ({ id: sc.id, name: sc.name, type: 'subchannel' }));
        } else {
          subData[channel.id] = [];
        }
        let supportsPush = false; let preferredPush = false;
        // Detection sources (descending priority)
        if (manifest.capabilities) {
          const caps = manifest.capabilities;
            if (Array.isArray(caps.update_modes) && caps.update_modes.includes('push')) supportsPush = true;
            if (caps.preferred_mode === 'push') preferredPush = true;
            if (caps.push_supported === true) supportsPush = true;
            if (caps.supports_push === true) supportsPush = true;
        }
        if (manifest.push && typeof manifest.push === 'object') {
          if (manifest.push.supports_push === true) supportsPush = true;
          if (manifest.push.active === true) supportsPush = true; // active push thread implies capability
        }
        if (manifest.supports_push === true) supportsPush = true; // top-level flag
        const rawFlag = manifest.supports_push || manifest.capabilities?.supports_push || manifest.capabilities?.push_supported;
        pushCaps[channel.id] = { supportsPush, preferredPush, rawFlag: !!rawFlag };
        if (typeof window !== 'undefined') {
          window.__mimirPushDebug = window.__mimirPushDebug || { manifests: {}, eval: [] };
          window.__mimirPushDebug.manifests[channel.id] = manifest;
        }
      } catch (err) {
        supportInfo[channel.id] = false;
        requirementsInfo[channel.id] = { requires_subchannel_selection: false };
        subData[channel.id] = [];
        pushCaps[channel.id] = { supportsPush: false, preferredPush: false };
      }
    }
    setSubChannelSupport(supportInfo);
    setSubChannelRequirements(requirementsInfo);
    setAvailableSubChannels(subData);
    setChannelPushCapabilities(pushCaps);
    setLoadingSubChannels(false);
    setCapabilitiesLoaded(true);
    evaluatePushSelectable(formData.channels, pushCaps, true);
    if (typeof window !== 'undefined') {
      window.__mimirPushDebug = window.__mimirPushDebug || { manifests: {}, eval: [] };
      window.__mimirPushDebug.capabilityMap = pushCaps;
      // eslint-disable-next-line no-console
      console.log('[SceneForm] Capability map:', pushCaps);
    }
  }, [channels, formData.channels, evaluatePushSelectable]);

  useEffect(() => { loadCapabilities(); }, [loadCapabilities]);
  useEffect(() => { 
    evaluatePushSelectable(formData.channels, channelPushCapabilities, capabilitiesLoaded); 
    if (typeof window !== 'undefined') {
      window.__mimirPushDebug = window.__mimirPushDebug || { manifests: {}, eval: [] };
      window.__mimirPushDebug.eval.push({ ts: Date.now(), assignments: formData.channels, caps: channelPushCapabilities, loaded: capabilitiesLoaded });
    }
  }, [formData.channels, channelPushCapabilities, capabilitiesLoaded, evaluatePushSelectable]);


  const handleScheduleChange = (field, value) => {
    setScheduleData(prev => ({
      ...prev,
      [field]: field === 'freq_value' ? Math.max(1, parseInt(value) || 1) : value
    }));
    setScheduleModified(true);
  };

  const createSchedule = async () => {
    if (!scene?.id || !scheduleData.freq_value || scheduleData.freq_value < 1) return;
    try {
      setScheduleLoading(true);
      const jobData = {
        name: `Auto-refresh ${formData.name || scene.name}`,
        description: `Automatically refresh scene every ${scheduleData.freq_value} ${scheduleData.freq_unit}(s)`,
        enabled: scheduleData.enabled,
        freq_unit: scheduleData.freq_unit,
        freq_value: parseInt(scheduleData.freq_value),
        action_type: 'refresh_scene',
        scene_ids: [scene.id],
        refresh_method: 'content_refresh'
      };
      const resp = await api.createSchedulerJob(jobData);
      setCurrentSchedule(resp.data);
    } finally { setScheduleLoading(false); }
  };

  const updateSchedule = async () => {
    if (!currentSchedule?.id || !scheduleData.freq_value || scheduleData.freq_value < 1) return;
    try {
      setScheduleLoading(true);
      const updates = { freq_unit: scheduleData.freq_unit, freq_value: parseInt(scheduleData.freq_value), enabled: scheduleData.enabled };
      const resp = await api.updateSchedulerJob(currentSchedule.id, updates);
      const updated = resp.data;
      setCurrentSchedule(updated);
      setScheduleData({ freq_unit: updated.freq_unit, freq_value: updated.freq_value, enabled: updated.enabled });
      setScheduleModified(false);
    } catch (err) {
      if (currentSchedule) {
        setScheduleData({ freq_unit: currentSchedule.freq_unit, freq_value: currentSchedule.freq_value, enabled: currentSchedule.enabled });
      }
    } finally { setScheduleLoading(false); }
  };

  const deleteSchedule = async () => {
    if (!currentSchedule?.id) return;
    try {
      setScheduleLoading(true);
      await api.deleteSchedulerJob(currentSchedule.id);
      setCurrentSchedule(null);
      setScheduleData({ freq_unit: 'hour', freq_value: 1, enabled: true });
      setScheduleModified(false);
    } finally { setScheduleLoading(false); }
  };

  // Form validation
  const runValidation = useCallback(() => {
    // Purely compute; caller responsible for setting state
    return validateForm(formData, subChannelRequirements, availableSubChannels, channels);
  }, [formData, subChannelRequirements, availableSubChannels, channels]);

  // Maintain validationErrors via effect so we don't trigger setState during render
  useEffect(() => {
    const errs = runValidation();
    // Only update state if changed to prevent unnecessary renders
    setValidationErrors(prev => {
      const changed = prev.length !== errs.length || prev.some((e,i)=> e !== errs[i]);
      return changed ? errs : prev;
    });
  }, [runValidation]);

  // Pure validity check (no side effects)
  const isFormValid = () => validationErrors.length === 0;

  // Submit logic
  const save = async () => {
    setLoading(true);
    setValidationErrors([]);
    const errs = runValidation();
    if (errs.length > 0) { setLoading(false); return; }
    try {
  // Ensure latest validation before save
  const currentErrs = runValidation();
  if (currentErrs.length) { setValidationErrors(currentErrs); setLoading(false); return; }
  const payload = buildPayload(formData);
  if (scene) await api.updateScene(scene.id, payload); else await api.createScene(payload);
      onClose && onClose();
    } catch (error) {
      if (error.response?.data?.detail) {
        if (Array.isArray(error.response.data.detail)) setValidationErrors(error.response.data.detail);
        else setValidationErrors([error.response.data.detail]);
      } else setValidationErrors(['An error occurred while saving the scene']);
    } finally { setLoading(false); }
  };

  return {
    formData,
    setFormData,
    validationErrors,
    loading,
    subChannelSupport,
    subChannelRequirements,
    availableSubChannels,
    channelPushCapabilities,
    loadingSubChannels,
    pushSelectable,
    pushSelectableReason,
    scheduleData,
    currentSchedule,
    scheduleLoading,
    scheduleModified,
    handleScheduleChange,
    createSchedule,
    updateSchedule,
    deleteSchedule,
    isFormValid,
    save,
    setValidationErrors
  };
}
