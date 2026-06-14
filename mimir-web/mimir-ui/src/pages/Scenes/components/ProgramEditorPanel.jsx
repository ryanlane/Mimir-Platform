import React, { useEffect, useRef, useState } from 'react';
import { X, ChevronDown, ChevronUp, Save, Image, Music2, Globe, Package, Radio, Trash2, ArrowUp, ArrowDown } from 'lucide-react';
import { useSceneFormLogic } from '../useSceneFormLogic';
import ValidationErrors from './ValidationErrors.jsx';
import DistributionModeSelector from './DistributionModeSelector.jsx';
import UpdateStrategySelector from './UpdateStrategySelector.jsx';
import ScheduleEditor from './ScheduleEditor.jsx';
import Button from '../../../components/Button/Button';
import './ProgramEditorPanel.css';

function getChannelType(channel) {
  const s = [channel?.name, channel?.id, channel?.plugin_id, channel?.type]
    .filter(Boolean).join(' ').toLowerCase();
  if (/photo|gallery|frame|image/.test(s)) return 'photo';
  if (/spotify|music|audio|sound/.test(s)) return 'music';
  if (/web|browser|url|http/.test(s)) return 'web';
  if (/radio|stream|live/.test(s)) return 'stream';
  return 'generic';
}

const TYPE_ICONS = { photo: Image, music: Music2, web: Globe, stream: Radio, generic: Package };

function SourceCompositionPreview({ assignments, channels }) {
  if (!assignments?.length) {
    return (
      <div className="pep-composition-empty">
        Add sources below to build your program
      </div>
    );
  }
  return (
    <div className="pep-composition-strip">
      {assignments.map((assignment, i) => {
        const chId = typeof assignment === 'string' ? assignment : assignment.channel_id;
        const ch = channels.find(c => c.id === chId);
        const type = getChannelType(ch);
        const Icon = TYPE_ICONS[type] || Package;
        return (
          <React.Fragment key={`${chId}-${i}`}>
            {i > 0 && <span className="pep-composition-arrow" aria-hidden="true">→</span>}
            <div className="pep-composition-tile">
              <Icon size={12} />
              <span>{ch?.name || chId}</span>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}

function SourceWell({ assignments, channels, subChannelSupport, availableSubChannels, loadingSubChannels, onChange }) {
  if (!assignments?.length) {
    return <div className="pep-well-empty">No sources added</div>;
  }

  const move = (index, dir) => {
    const next = [...assignments];
    const swapIdx = index + dir;
    if (swapIdx < 0 || swapIdx >= next.length) return;
    [next[index], next[swapIdx]] = [next[swapIdx], next[index]];
    onChange(next);
  };

  const remove = (index) => {
    onChange(assignments.filter((_, i) => i !== index));
  };

  const setSubchannel = (index, subId) => {
    const next = assignments.map((a, i) =>
      i === index ? { ...a, subchannel_id: subId || null } : a
    );
    onChange(next);
  };

  return (
    <div className="pep-well">
      {assignments.map((assignment, i) => {
        const chId = typeof assignment === 'string' ? assignment : assignment.channel_id;
        const subId = assignment.subchannel_id || null;
        const ch = channels.find(c => c.id === chId);
        const type = getChannelType(ch);
        const Icon = TYPE_ICONS[type] || Package;
        const supportsSubchannels = subChannelSupport?.[chId];
        const subchannels = availableSubChannels?.[chId] || [];

        return (
          <div key={`${chId}-${i}`} className="pep-well-item-group">
            <div className="pep-well-item">
              <span className="pep-well-index">{i + 1}</span>
              <Icon size={13} className="pep-well-type-icon" />
              <span className="pep-well-name">{ch?.name || chId}</span>
              <div className="pep-well-controls">
                <button type="button" className="pep-well-btn" onClick={() => move(i, -1)} disabled={i === 0} aria-label="Move up">
                  <ArrowUp size={12} />
                </button>
                <button type="button" className="pep-well-btn" onClick={() => move(i, 1)} disabled={i === assignments.length - 1} aria-label="Move down">
                  <ArrowDown size={12} />
                </button>
                <button type="button" className="pep-well-btn pep-well-btn--remove" onClick={() => remove(i)} aria-label="Remove source">
                  <Trash2 size={12} />
                </button>
              </div>
            </div>

            {supportsSubchannels && (
              <div className="pep-well-subchannel">
                <label className="pep-well-subchannel-label">Gallery</label>
                {loadingSubChannels ? (
                  <span className="pep-well-subchannel-loading">Loading galleries…</span>
                ) : (
                  <select
                    className="pep-well-subchannel-select"
                    value={subId || ''}
                    onChange={e => setSubchannel(i, e.target.value || null)}
                  >
                    <option value="">All galleries</option>
                    {subchannels.map(sc => (
                      <option key={sc.id} value={sc.id}>{sc.name}{sc.image_count != null ? ` (${sc.image_count})` : ''}</option>
                    ))}
                  </select>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function SourcePicker({ channels, currentAssignments, onAdd }) {
  const assignedIds = new Set(
    currentAssignments.map(a => typeof a === 'string' ? a : a.channel_id)
  );
  const unassigned = channels.filter(c => !assignedIds.has(c.id));

  if (!unassigned.length) {
    return <div className="pep-picker-empty">All available sources added</div>;
  }

  return (
    <div className="pep-picker">
      {unassigned.map(ch => {
        const type = getChannelType(ch);
        const Icon = TYPE_ICONS[type] || Package;
        return (
          <button
            key={ch.id}
            type="button"
            className="pep-picker-item"
            onClick={() => onAdd({ channel_id: ch.id, subchannel_id: null })}
          >
            <Icon size={13} />
            <span>{ch.name}</span>
            <span className="pep-picker-add">+</span>
          </button>
        );
      })}
    </div>
  );
}

export function ProgramEditorPanel({ scene, channels = [], onClose }) {
  const nameRef = useRef(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  const {
    formData,
    setFormData,
    validationErrors,
    loading,
    subChannelSupport,
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
    save,
  } = useSceneFormLogic({ scene, channels, onClose });

  useEffect(() => {
    const t = setTimeout(() => nameRef.current?.focus(), 50);
    return () => clearTimeout(t);
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    save();
  };

  const handleAddSource = (assignment) => {
    setFormData(prev => ({ ...prev, channels: [...prev.channels, assignment] }));
    setPickerOpen(false);
  };

  const handleReorderSources = (newAssignments) => {
    setFormData(prev => ({ ...prev, channels: newAssignments }));
  };

  return (
    <aside className="program-editor-panel">
      <div className="pep-header">
        <h2 className="pep-title">{scene ? `Edit: ${scene.name}` : 'New Program'}</h2>
        <button className="pep-close" onClick={onClose} aria-label="Cancel and close">
          <X size={14} />
        </button>
      </div>

      <form className="pep-body" onSubmit={handleSubmit}>
        <div className="pep-section">
          <label className="pep-field-label" htmlFor="pep-name">Name</label>
          <input
            id="pep-name"
            ref={nameRef}
            type="text"
            className="pep-name-input"
            value={formData.name}
            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            placeholder="Program name"
            required
          />
        </div>

        <div className="pep-section">
          <div className="pep-section-label">COMPOSITION PREVIEW</div>
          <SourceCompositionPreview assignments={formData.channels} channels={channels} />
        </div>

        <div className="pep-section">
          <div className="pep-section-label-row">
            <span className="pep-section-label">SOURCES</span>
            <button
              type="button"
              className="pep-picker-toggle"
              onClick={() => setPickerOpen(v => !v)}
            >
              {pickerOpen ? 'Cancel' : '+ Add Source'}
            </button>
          </div>
          {pickerOpen && (
            <SourcePicker
              channels={channels}
              currentAssignments={formData.channels}
              onAdd={handleAddSource}
            />
          )}
          <SourceWell
            assignments={formData.channels}
            channels={channels}
            subChannelSupport={subChannelSupport}
            availableSubChannels={availableSubChannels}
            loadingSubChannels={loadingSubChannels}
            onChange={handleReorderSources}
          />
        </div>

        <ValidationErrors errors={validationErrors} />

        <div className="pep-advanced-toggle" onClick={() => setAdvancedOpen(v => !v)}>
          <span>Advanced settings</span>
          {advancedOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>

        {advancedOpen && (
          <div className="pep-section pep-section--advanced">
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
          </div>
        )}

        <div className="pep-footer">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={loading}
            disabled={loading || !isFormValid}
          >
            <Save size={14} />
            {scene ? 'Save Changes' : 'Save Program'}
          </Button>
        </div>
      </form>
    </aside>
  );
}

export default ProgramEditorPanel;
