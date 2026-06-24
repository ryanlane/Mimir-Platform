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

import React, { useState } from 'react';
import { Database, AlertTriangle } from 'lucide-react';
import { api } from '../../services/api';
import './AdminOperations.css';

const AdminOperations = () => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Admin operations state
  const [showResetConfirmation, setShowResetConfirmation] = useState(false);
  const [resetStep, setResetStep] = useState(0); // 0: initial, 1: warning, 2: final confirmation
  const [resetLoading, setResetLoading] = useState(false);
  const [resetResults, setResetResults] = useState(null);
  const [orphanedChannels, setOrphanedChannels] = useState(null);
  const [checkingOrphaned, setCheckingOrphaned] = useState(false);

  // Admin Operations Handlers
  const handleCheckOrphanedChannels = async () => {
    setCheckingOrphaned(true);
    try {
      const response = await api.getOrphanedChannels();
      setOrphanedChannels(response.data);
    } catch (error) {
      console.error('Error checking orphaned channels:', error);
      setOrphanedChannels({ error: 'Failed to check orphaned channels' });
    } finally {
      setCheckingOrphaned(false);
    }
  };

  const handleResetChannelsDatabase = async () => {
    if (resetStep === 0) {
      // First step: show initial warning
      setShowResetConfirmation(true);
      setResetStep(1);
      return;
    }

    if (resetStep === 1) {
      // Second step: final confirmation
      setResetStep(2);
      return;
    }

    // Final step: actually perform the reset
    setResetLoading(true);
    try {
      const response = await api.resetChannelsDatabase();
      setResetResults(response.data);
      setResetStep(0);
      setShowResetConfirmation(false);
      
      // Refresh any cached data
      if (orphanedChannels) {
        await handleCheckOrphanedChannels();
      }
      
      console.log('✅ Channels database reset successfully:', response.data);
    } catch (error) {
      console.error('❌ Error resetting channels database:', error);
      setResetResults({ 
        error: 'Failed to reset channels database', 
        details: error.response?.data?.detail || error.message 
      });
    } finally {
      setResetLoading(false);
    }
  };

  const handleCancelReset = () => {
    setShowResetConfirmation(false);
    setResetStep(0);
  };

  const handleDismissResults = () => {
    setResetResults(null);
  };

  return (
    <div className="admin-operations">
      <div className="admin-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="admin-title">
          <Database size={16} />
          <span>Admin Operations</span>
        </div>
        <div className="admin-warning-badge">
          <AlertTriangle size={14} />
          <span>Destructive Operations</span>
        </div>
        <button className="expand-button">
          {isExpanded ? '−' : '+'}
        </button>
      </div>
      
      {isExpanded && (
        <div className="admin-content">
          <div className="admin-section">
            <div className="admin-operation">
              <div className="operation-info">
                <h4>Check Orphaned Channels</h4>
                <p className="operation-description">
                  Find channels in the database that no longer exist in the filesystem.
                </p>
              </div>
              <button 
                className="btn btn-secondary"
                onClick={handleCheckOrphanedChannels}
                disabled={checkingOrphaned}
              >
                {checkingOrphaned ? 'Checking...' : 'Check Orphaned'}
              </button>
            </div>

            {orphanedChannels && (
              <div className="orphaned-results">
                {orphanedChannels.error ? (
                  <div className="error-message">
                    <AlertTriangle size={16} />
                    <span>{orphanedChannels.error}</span>
                  </div>
                ) : (
                  <div className="orphaned-channels">
                    <h5>Orphaned Channels Found: {orphanedChannels.length}</h5>
                    {orphanedChannels.length > 0 ? (
                      <ul className="orphaned-list">
                        {orphanedChannels.map((channel, index) => (
                          <li key={index} className="orphaned-item">
                            <strong>{channel.id}</strong>
                            {channel.name && <span> - {channel.name}</span>}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="no-orphaned">✅ No orphaned channels found</p>
                    )}
                  </div>
                )}
              </div>
            )}

            <div className="admin-operation danger-operation">
              <div className="operation-info">
                <h4>Reset Channels Database</h4>
                <p className="operation-description">
                  <strong>⚠️ DESTRUCTIVE:</strong> Clears the channels database and rebuilds it from the filesystem. 
                  This will resolve channel ID mismatches but may break scene assignments.
                </p>
              </div>
              <button 
                className="btn btn-danger"
                onClick={handleResetChannelsDatabase}
                disabled={resetLoading}
              >
                {resetLoading ? 'Resetting...' : 'Reset Database'}
              </button>
            </div>

            {/* Reset Confirmation Modal */}
            {showResetConfirmation && (
              <div className="modal-overlay">
                <div className="modal reset-confirmation-modal">
                  <div className="modal-header">
                    <h3>
                      <AlertTriangle size={24} />
                      {resetStep === 1 ? 'Confirm Database Reset' : 'Final Confirmation Required'}
                    </h3>
                  </div>
                  
                  <div className="modal-body">
                    {resetStep === 1 ? (
                      <div className="warning-content">
                        <div className="warning-icon">
                          <AlertTriangle size={48} />
                        </div>
                        <div className="warning-text">
                          <h4>This operation will:</h4>
                          <ul className="warning-list">
                            <li>🗑️ Delete ALL channel data from the database</li>
                            <li>📂 Rebuild from current filesystem channels</li>
                            <li>🔄 Update channel IDs to match config.json files</li>
                            <li>⚠️ May break existing scene assignments</li>
                          </ul>
                          <p><strong>This action cannot be undone.</strong></p>
                        </div>
                      </div>
                    ) : (
                      <div className="final-confirmation">
                        <p className="final-warning">
                          <strong>Are you absolutely sure?</strong>
                        </p>
                        <p>Type "RESET" to confirm:</p>
                        <input 
                          type="text" 
                          id="reset-confirmation-input"
                          placeholder="Type RESET here"
                          className="confirmation-input"
                        />
                      </div>
                    )}
                  </div>
                  
                  <div className="modal-footer">
                    <button className="btn btn-secondary" onClick={handleCancelReset}>
                      Cancel
                    </button>
                    {resetStep === 1 ? (
                      <button className="btn btn-warning" onClick={handleResetChannelsDatabase}>
                        I Understand, Continue
                      </button>
                    ) : (
                      <button 
                        className="btn btn-danger"
                        onClick={() => {
                          const input = document.getElementById('reset-confirmation-input');
                          if (input?.value === 'RESET') {
                            handleResetChannelsDatabase();
                          } else {
                            alert('Please type "RESET" to confirm');
                          }
                        }}
                      >
                        Reset Database Now
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Reset Results */}
            {resetResults && (
              <div className="reset-results">
                <div className="results-header">
                  <h4>Reset Results</h4>
                  <button className="btn btn-sm btn-secondary" onClick={handleDismissResults}>
                    Dismiss
                  </button>
                </div>
                
                {resetResults.error ? (
                  <div className="error-message">
                    <AlertTriangle size={16} />
                    <div>
                      <strong>Error:</strong> {resetResults.error}
                      {resetResults.details && <p>{resetResults.details}</p>}
                    </div>
                  </div>
                ) : (
                  <div className="success-results">
                    <div className="success-summary">
                      <h5>✅ Database Reset Successful</h5>
                      <div className="results-stats">
                        <div className="stat-item">
                          <span className="stat-number">{resetResults.removed?.length || 0}</span>
                          <span className="stat-label">Removed</span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-number">{resetResults.added?.length || 0}</span>
                          <span className="stat-label">Added</span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-number">{resetResults.kept?.length || 0}</span>
                          <span className="stat-label">Kept</span>
                        </div>
                      </div>
                    </div>
                    
                    {resetResults.scene_warnings && resetResults.scene_warnings.length > 0 && (
                      <div className="scene-warnings">
                        <h6>⚠️ Scene Assignment Warnings</h6>
                        <ul>
                          {resetResults.scene_warnings.map((warning, index) => (
                            <li key={index}>{warning}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminOperations;
