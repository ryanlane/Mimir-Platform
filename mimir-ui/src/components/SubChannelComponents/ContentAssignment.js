import React, { useState } from 'react';
import { 
  Minus, Search, Filter,
  Image, FileText, Play, Grid, List, CheckSquare,
  ArrowRight, RefreshCw, AlertTriangle
} from 'lucide-react';
import './ContentAssignment.css';

const ContentAssignment = ({
  sourceContent = [],
  targetSubChannels = [],
  onAssign,
  onUnassign,
  onMove,
  onCopy,
  onBulkAssign,
  multiple = true,
  showPreview = true,
  showStats = true,
  allowMove = true,
  allowCopy = true,
  contentType = 'image',
  loading = false,
  disabled = false,
  className = ""
}) => {
  const [selectedContent, setSelectedContent] = useState([]);
  const [selectedSubChannels, setSelectedSubChannels] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterAssigned, setFilterAssigned] = useState('all'); // all, assigned, unassigned
  const [viewMode, setViewMode] = useState('grid'); // grid, list
  const [showBulkActions, setShowBulkActions] = useState(false);
  const [bulkAction, setBulkAction] = useState('assign'); // assign, unassign, move, copy

  // Filter and search content
  const filteredContent = sourceContent.filter(content => {
    // Search filter
    if (searchTerm) {
      const searchLower = searchTerm.toLowerCase();
      const matchesName = content.name?.toLowerCase().includes(searchLower);
      const matchesDescription = content.description?.toLowerCase().includes(searchLower);
      const matchesTags = content.tags?.some(tag => tag.toLowerCase().includes(searchLower));
      
      if (!matchesName && !matchesDescription && !matchesTags) {
        return false;
      }
    }

    // Assignment filter
    if (filterAssigned !== 'all') {
      const isAssigned = content.assignedSubChannels?.length > 0;
      if (filterAssigned === 'assigned' && !isAssigned) return false;
      if (filterAssigned === 'unassigned' && isAssigned) return false;
    }

    return true;
  });

  const handleContentSelect = (contentId) => {
    if (multiple) {
      setSelectedContent(prev => 
        prev.includes(contentId) 
          ? prev.filter(id => id !== contentId)
          : [...prev, contentId]
      );
    } else {
      setSelectedContent([contentId]);
    }
  };

  const handleSubChannelSelect = (subChannelId) => {
    setSelectedSubChannels(prev => 
      prev.includes(subChannelId) 
        ? prev.filter(id => id !== subChannelId)
        : [...prev, subChannelId]
    );
  };

  const handleSelectAllContent = () => {
    if (selectedContent.length === filteredContent.length) {
      setSelectedContent([]);
    } else {
      setSelectedContent(filteredContent.map(c => c.id));
    }
  };

  const handleSelectAllSubChannels = () => {
    if (selectedSubChannels.length === targetSubChannels.length) {
      setSelectedSubChannels([]);
    } else {
      setSelectedSubChannels(targetSubChannels.map(sc => sc.id));
    }
  };

  const handleSingleUnassign = (contentId, subChannelId) => {
    if (onUnassign) {
      onUnassign([contentId], [subChannelId]);
    }
  };

  const handleBulkAction = () => {
    if (selectedContent.length === 0 || selectedSubChannels.length === 0) return;

    switch (bulkAction) {
      case 'assign':
        onAssign?.(selectedContent, selectedSubChannels);
        break;
      case 'unassign':
        onUnassign?.(selectedContent, selectedSubChannels);
        break;
      case 'move':
        onMove?.(selectedContent, selectedSubChannels);
        break;
      case 'copy':
        onCopy?.(selectedContent, selectedSubChannels);
        break;
      default:
        break;
    }

    // Clear selections after action
    setSelectedContent([]);
    setSelectedSubChannels([]);
    setShowBulkActions(false);
  };

  const getContentIcon = (content) => {
    switch (contentType) {
      case 'image':
        return <Image size={16} />;
      case 'video':
        return <Play size={16} />;
      default:
        return <FileText size={16} />;
    }
  };

  const getAssignmentStatus = (content) => {
    const assignedCount = content.assignedSubChannels?.length || 0;
    const totalCount = targetSubChannels.length;
    
    if (assignedCount === 0) return 'unassigned';
    if (assignedCount === totalCount) return 'fully-assigned';
    return 'partially-assigned';
  };

  const renderContentItem = (content) => {
    const isSelected = selectedContent.includes(content.id);
    const status = getAssignmentStatus(content);
    
    if (viewMode === 'grid') {
      return (
        <div
          key={content.id}
          className={`content-item grid-item ${isSelected ? 'selected' : ''} ${status}`}
          onClick={() => handleContentSelect(content.id)}
        >
          {showPreview && content.thumbnailUrl && (
            <div className="content-preview">
              <img src={content.thumbnailUrl} alt={content.name} />
            </div>
          )}
          
          <div className="content-info">
            <div className="content-header">
              {getContentIcon(content)}
              <span className="content-name">{content.name}</span>
            </div>
            
            {content.assignedSubChannels?.length > 0 && (
              <div className="assignment-badges">
                {content.assignedSubChannels.slice(0, 2).map(sc => (
                  <span key={sc.id} className="assignment-badge">
                    {sc.name}
                  </span>
                ))}
                {content.assignedSubChannels.length > 2 && (
                  <span className="assignment-badge more">
                    +{content.assignedSubChannels.length - 2}
                  </span>
                )}
              </div>
            )}
          </div>
          
          {multiple && (
            <div className={`content-checkbox ${isSelected ? 'checked' : ''}`}>
              <CheckSquare size={16} />
            </div>
          )}
        </div>
      );
    } else {
      return (
        <div
          key={content.id}
          className={`content-item list-item ${isSelected ? 'selected' : ''} ${status}`}
          onClick={() => handleContentSelect(content.id)}
        >
          {multiple && (
            <div className={`content-checkbox ${isSelected ? 'checked' : ''}`}>
              <CheckSquare size={16} />
            </div>
          )}
          
          <div className="content-icon">
            {getContentIcon(content)}
          </div>
          
          <div className="content-details">
            <div className="content-name">{content.name}</div>
            {content.description && (
              <div className="content-description">{content.description}</div>
            )}
          </div>
          
          <div className="assignment-status">
            {content.assignedSubChannels?.length || 0} / {targetSubChannels.length}
          </div>
          
          <div className="content-actions">
            {content.assignedSubChannels?.map(sc => (
              <button
                key={sc.id}
                type="button"
                className="unassign-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  handleSingleUnassign(content.id, sc.id);
                }}
                title={`Remove from ${sc.name}`}
              >
                <Minus size={12} />
              </button>
            ))}
          </div>
        </div>
      );
    }
  };

  const renderSubChannelItem = (subChannel) => {
    const isSelected = selectedSubChannels.includes(subChannel.id);
    
    return (
      <div
        key={subChannel.id}
        className={`subchannel-item ${isSelected ? 'selected' : ''}`}
        onClick={() => handleSubChannelSelect(subChannel.id)}
      >
        <div className={`subchannel-checkbox ${isSelected ? 'checked' : ''}`}>
          <CheckSquare size={16} />
        </div>
        
        <div className="subchannel-info">
          <div className="subchannel-name">{subChannel.name}</div>
          <div className="subchannel-stats">
            {subChannel.contentCount || 0} {contentType}s
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={`content-assignment ${disabled ? 'disabled' : ''} ${className}`}>
      {/* Header */}
      <div className="assignment-header">
        <h3>Content Assignment</h3>
        
        <div className="header-actions">
          <div className="view-toggle">
            <button
              type="button"
              className={viewMode === 'grid' ? 'active' : ''}
              onClick={() => setViewMode('grid')}
            >
              <Grid size={16} />
            </button>
            <button
              type="button"
              className={viewMode === 'list' ? 'active' : ''}
              onClick={() => setViewMode('list')}
            >
              <List size={16} />
            </button>
          </div>
          
          {multiple && (
            <button
              type="button"
              className="bulk-toggle"
              onClick={() => setShowBulkActions(!showBulkActions)}
              disabled={selectedContent.length === 0}
            >
              Bulk Actions ({selectedContent.length})
            </button>
          )}
        </div>
      </div>

      {/* Search and Filters */}
      <div className="assignment-controls">
        <div className="search-container">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder={`Search ${contentType}s...`}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
        
        <div className="filter-container">
          <Filter size={16} className="filter-icon" />
          <select 
            value={filterAssigned} 
            onChange={(e) => setFilterAssigned(e.target.value)}
            className="filter-select"
          >
            <option value="all">All Content</option>
            <option value="assigned">Assigned</option>
            <option value="unassigned">Unassigned</option>
          </select>
        </div>
      </div>

      {/* Bulk Actions Panel */}
      {showBulkActions && multiple && (
        <div className="bulk-actions-panel">
          <div className="bulk-action-select">
            <select 
              value={bulkAction} 
              onChange={(e) => setBulkAction(e.target.value)}
            >
              <option value="assign">Assign to</option>
              <option value="unassign">Unassign from</option>
              {allowMove && <option value="move">Move to</option>}
              {allowCopy && <option value="copy">Copy to</option>}
            </select>
          </div>
          
          <div className="selection-summary">
            {selectedContent.length} content items, {selectedSubChannels.length} sub-channels
          </div>
          
          <button
            type="button"
            className="execute-bulk-btn"
            onClick={handleBulkAction}
            disabled={selectedContent.length === 0 || selectedSubChannels.length === 0 || loading}
          >
            {loading ? <RefreshCw size={16} className="spinning" /> : <ArrowRight size={16} />}
            Execute
          </button>
        </div>
      )}

      {/* Main Content */}
      <div className="assignment-main">
        {/* Content List */}
        <div className="content-section">
          <div className="section-header">
            <h4>Content ({filteredContent.length})</h4>
            {multiple && (
              <button
                type="button"
                className="select-all-btn"
                onClick={handleSelectAllContent}
              >
                {selectedContent.length === filteredContent.length ? 'Deselect All' : 'Select All'}
              </button>
            )}
          </div>
          
          <div className={`content-list ${viewMode}`}>
            {filteredContent.length === 0 ? (
              <div className="empty-state">
                <AlertTriangle size={24} />
                <span>No content found</span>
              </div>
            ) : (
              filteredContent.map(renderContentItem)
            )}
          </div>
        </div>

        {/* Assignment Arrow */}
        <div className="assignment-arrow">
          <ArrowRight size={24} />
        </div>

        {/* Sub-Channels List */}
        <div className="subchannels-section">
          <div className="section-header">
            <h4>Sub-Channels ({targetSubChannels.length})</h4>
            <button
              type="button"
              className="select-all-btn"
              onClick={handleSelectAllSubChannels}
            >
              {selectedSubChannels.length === targetSubChannels.length ? 'Deselect All' : 'Select All'}
            </button>
          </div>
          
          <div className="subchannels-list">
            {targetSubChannels.length === 0 ? (
              <div className="empty-state">
                <AlertTriangle size={24} />
                <span>No sub-channels available</span>
              </div>
            ) : (
              targetSubChannels.map(renderSubChannelItem)
            )}
          </div>
        </div>
      </div>

      {/* Stats */}
      {showStats && (
        <div className="assignment-stats">
          <div className="stat-item">
            <span className="stat-label">Total Content:</span>
            <span className="stat-value">{sourceContent.length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Assigned:</span>
            <span className="stat-value">
              {sourceContent.filter(c => c.assignedSubChannels?.length > 0).length}
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Unassigned:</span>
            <span className="stat-value">
              {sourceContent.filter(c => !c.assignedSubChannels?.length).length}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ContentAssignment;
