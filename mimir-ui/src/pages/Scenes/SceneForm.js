import React from 'react';
import { Save } from 'lucide-react';
import './SceneForm.css';
// Extracted presentational components
// Explicit .jsx extensions to avoid potential bundler resolution ambiguity
import ValidationErrors from './components/ValidationErrors.jsx';
import DistributionModeSelector from './components/DistributionModeSelector.jsx';
import UpdateStrategySelector from './components/UpdateStrategySelector.jsx';
import ChannelSelector from './components/ChannelSelector.jsx';
import ScheduleEditor from './components/ScheduleEditor.jsx';
import { useSceneFormLogic } from './useSceneFormLogic';
import Modal from '../../components/Modal/Modal';
import Button from '../../components/Button/Button';

const SceneForm = ({ scene, channels, onClose }) => {
  // Debug render counter
  if (typeof window !== 'undefined') {
    window.__sceneFormRenders = (window.__sceneFormRenders || 0) + 1;
    // eslint-disable-next-line no-console
    console.log(`[SceneForm] Render count: ${window.__sceneFormRenders}`);
  }
  const {
    formData,
    setFormData,
    validationErrors,
    loading,
    subChannelSupport,
    subChannelRequirements,
    availableSubChannels,
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
    save
  } = useSceneFormLogic({ scene, channels, onClose });

  const handleSubmit = (e) => { e.preventDefault(); save(); };

  /* Schedule functions temporarily disabled
  const handleScheduleChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      schedule: prev.schedule ? 
        { ...prev.schedule, [field]: value } :
        { days: ['mon', 'tue', 'wed', 'thu', 'fri'], start: '09:00', end: '17:00', [field]: value }
    }));
  };

  const removeSchedule = () => {
    setFormData(prev => ({ ...prev, schedule: null }));
  };
  */

  // Runtime sanity checks – if any imported component failed to load it would cause React 301.
  if (!ValidationErrors || !ChannelSelector || !DistributionModeSelector || !UpdateStrategySelector || !ScheduleEditor) {
    console.error('[SceneForm] One or more sub components failed to import:', {
      ValidationErrors: !!ValidationErrors,
      ChannelSelector: !!ChannelSelector,
      DistributionModeSelector: !!DistributionModeSelector,
      UpdateStrategySelector: !!UpdateStrategySelector,
      ScheduleEditor: !!ScheduleEditor
    });
    return (
      <Modal
        isOpen={true}
        onClose={onClose}
        title="Scene Form Load Error"
        size="medium"
      >
        <div className="scene-form">
          <div className="scene-form-body">
            <p>Required components failed to load. Check console for details.</p>
            <div style={{ marginTop: '1rem' }}>
              <Button size="sm" variant="secondary" onClick={onClose}>Close</Button>
            </div>
          </div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={scene ? 'Edit Scene' : 'Create Scene'}
      size="medium"
    >
      <div className="scene-form">
        <form onSubmit={handleSubmit} className="scene-form-body">
          <div className="form-group">
            <label className="form-label">Scene Name</label>
            <input
              type="text"
              className="form-input"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              required
            />
          </div>

          <ValidationErrors errors={validationErrors} />

          <ChannelSelector
            channels={channels}
            assignments={formData.channels}
            subChannelSupport={subChannelSupport}
            availableSubChannels={availableSubChannels}
            subChannelRequirements={subChannelRequirements}
            loadingSubChannels={loadingSubChannels}
            onChange={(assignments) => setFormData(prev => ({ ...prev, channels: assignments }))}
          />

            <DistributionModeSelector
              value={formData.distribution_mode}
              onChange={(newMode) => setFormData(prev => ({ ...prev, distribution_mode: newMode }))}
            />

            <UpdateStrategySelector
              strategy={formData.update_strategy}
              fallbackSeconds={formData.push_fallback_poll_seconds}
              pushAllowed={pushSelectable}
              hasChannelSelected={formData.channels.length > 0}
              disabledReason={pushSelectableReason}
              onChange={({ strategy, fallbackSeconds }) =>
                setFormData(prev => ({
                  ...prev,
                  update_strategy: strategy,
                  ...(strategy === 'push'
                    ? { push_fallback_poll_seconds: fallbackSeconds }
                    : { push_fallback_poll_seconds: prev.push_fallback_poll_seconds })
                }))
              }
            />

            <ScheduleEditor
              currentSchedule={currentSchedule}
              scheduleData={scheduleData}
              scheduleModified={scheduleModified}
              loading={scheduleLoading}
              sceneId={scene?.id}
              onChange={handleScheduleChange}
              onCreate={createSchedule}
              onUpdate={updateSchedule}
              onDelete={deleteSchedule}
            />

          <div className="scene-form-footer">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            {(() => { const valid = isFormValid(); return (
              <Button
                type="submit"
                variant="primary"
                disabled={loading || !valid}
                icon={<Save size={16} aria-hidden="true" />}>
                {loading ? 'Saving...' : 'Save Scene'}
              </Button>
            ); })()}
          </div>
        </form>
      </div>
    </Modal>
  );
};

export default SceneForm;
