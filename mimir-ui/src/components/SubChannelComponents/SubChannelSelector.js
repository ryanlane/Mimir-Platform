import React, { useState, useEffect, useRef } from 'react';
import { ChevronDown, Search, Check, Plus, Filter } from 'lucide-react';
import './SubChannelSelector.css';

const SubChannelSelector = ({
  subChannels = [],
  selectedIds = [],
  onSelectionChange,
  multiple = false,
  placeholder = "Select sub-channels...",
  searchable = true,
  filterable = true,
  creatable = false,
  onCreate,
  disabled = false,
  maxHeight = "300px",
  groupByChannel = false,
  showChannelInfo = true,
  compact = false,
  className = ""
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [hoveredIndex, setHoveredIndex] = useState(-1);
  const dropdownRef = useRef(null);
  const searchInputRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (isOpen && searchable && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isOpen, searchable]);

  // Filter and search sub-channels
  const filteredSubChannels = subChannels.filter(subChannel => {
    // Search filter
    if (searchTerm) {
      const searchLower = searchTerm.toLowerCase();
      const matchesName = subChannel.name.toLowerCase().includes(searchLower);
      const matchesDescription = subChannel.description?.toLowerCase().includes(searchLower);
      const matchesTags = subChannel.tags?.some(tag => tag.toLowerCase().includes(searchLower));
      
      if (!matchesName && !matchesDescription && !matchesTags) {
        return false;
      }
    }

    // Type filter
    if (filterType !== 'all' && subChannel.type !== filterType) {
      return false;
    }

    return true;
  });

  // Group by channel if requested
  const groupedSubChannels = groupByChannel 
    ? filteredSubChannels.reduce((groups, subChannel) => {
        const channelName = subChannel.channelName || 'Unknown Channel';
        if (!groups[channelName]) {
          groups[channelName] = [];
        }
        groups[channelName].push(subChannel);
        return groups;
      }, {})
    : { 'All': filteredSubChannels };

  // Get unique types for filter
  const availableTypes = [...new Set(subChannels.map(sc => sc.type))];

  const handleToggle = () => {
    if (!disabled) {
      setIsOpen(!isOpen);
      setSearchTerm('');
      setHoveredIndex(-1);
    }
  };

  const handleSelect = (subChannel) => {
    if (multiple) {
      const isSelected = selectedIds.includes(subChannel.id);
      const newSelection = isSelected 
        ? selectedIds.filter(id => id !== subChannel.id)
        : [...selectedIds, subChannel.id];
      onSelectionChange(newSelection);
    } else {
      onSelectionChange([subChannel.id]);
      setIsOpen(false);
    }
  };

  const handleSelectAll = () => {
    if (selectedIds.length === filteredSubChannels.length) {
      onSelectionChange([]);
    } else {
      onSelectionChange(filteredSubChannels.map(sc => sc.id));
    }
  };

  const handleClear = () => {
    onSelectionChange([]);
  };

  const handleCreate = () => {
    if (onCreate && searchTerm.trim()) {
      onCreate(searchTerm.trim());
      setSearchTerm('');
    }
  };

  const getSelectedText = () => {
    if (selectedIds.length === 0) {
      return placeholder;
    }
    
    if (selectedIds.length === 1) {
      const selected = subChannels.find(sc => sc.id === selectedIds[0]);
      return selected ? selected.name : 'Unknown';
    }
    
    return `${selectedIds.length} selected`;
  };

  const renderSubChannelItem = (subChannel, index) => {
    const isSelected = selectedIds.includes(subChannel.id);
    const isHovered = hoveredIndex === index;

    return (
      <div
        key={subChannel.id}
        className={`selector-item ${isSelected ? 'selected' : ''} ${isHovered ? 'hovered' : ''}`}
        onClick={() => handleSelect(subChannel)}
        onMouseEnter={() => setHoveredIndex(index)}
      >
        {multiple && (
          <div className={`item-checkbox ${isSelected ? 'checked' : ''}`}>
            {isSelected && <Check size={12} />}
          </div>
        )}
        
        <div className="item-content">
          <div className="item-name">{subChannel.name}</div>
          {subChannel.description && !compact && (
            <div className="item-description">{subChannel.description}</div>
          )}
          {showChannelInfo && subChannel.channelName && (
            <div className="item-channel">{subChannel.channelName}</div>
          )}
        </div>

        {subChannel.imageCount > 0 && (
          <div className="item-count">
            {subChannel.imageCount}
          </div>
        )}
      </div>
    );
  };

  return (
    <div 
      ref={dropdownRef}
      className={`subchannel-selector ${disabled ? 'disabled' : ''} ${compact ? 'compact' : ''} ${className}`}
    >
      <div 
        className={`selector-trigger ${isOpen ? 'open' : ''}`}
        onClick={handleToggle}
      >
        <span className="trigger-text">{getSelectedText()}</span>
        <ChevronDown 
          size={compact ? 14 : 16} 
          className={`trigger-icon ${isOpen ? 'rotated' : ''}`} 
        />
      </div>

      {isOpen && (
        <div className="selector-dropdown" style={{ maxHeight }}>
          {/* Search and Filters */}
          {(searchable || filterable) && (
            <div className="selector-header">
              {searchable && (
                <div className="search-container">
                  <Search size={14} className="search-icon" />
                  <input
                    ref={searchInputRef}
                    type="text"
                    placeholder="Search sub-channels..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="search-input"
                  />
                </div>
              )}
              
              {filterable && availableTypes.length > 1 && (
                <div className="filter-container">
                  <Filter size={14} className="filter-icon" />
                  <select 
                    value={filterType} 
                    onChange={(e) => setFilterType(e.target.value)}
                    className="filter-select"
                  >
                    <option value="all">All Types</option>
                    {availableTypes.map(type => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}

          {/* Bulk Actions */}
          {multiple && filteredSubChannels.length > 0 && (
            <div className="selector-actions">
              <button 
                type="button"
                onClick={handleSelectAll}
                className="action-btn"
              >
                {selectedIds.length === filteredSubChannels.length ? 'Deselect All' : 'Select All'}
              </button>
              
              {selectedIds.length > 0 && (
                <button 
                  type="button"
                  onClick={handleClear}
                  className="action-btn secondary"
                >
                  Clear ({selectedIds.length})
                </button>
              )}
            </div>
          )}

          {/* Items List */}
          <div className="selector-items">
            {Object.keys(groupedSubChannels).length === 0 ? (
              <div className="no-results">
                <span>No sub-channels found</span>
                {creatable && searchTerm.trim() && (
                  <button 
                    type="button"
                    onClick={handleCreate}
                    className="create-btn"
                  >
                    <Plus size={14} />
                    Create "{searchTerm}"
                  </button>
                )}
              </div>
            ) : (
              Object.entries(groupedSubChannels).map(([groupName, items]) => (
                <div key={groupName} className="item-group">
                  {groupByChannel && Object.keys(groupedSubChannels).length > 1 && (
                    <div className="group-header">{groupName}</div>
                  )}
                  {items.map((subChannel, index) => 
                    renderSubChannelItem(subChannel, index)
                  )}
                </div>
              ))
            )}
          </div>

          {/* Create Option */}
          {creatable && searchTerm.trim() && filteredSubChannels.length === 0 && (
            <div className="selector-footer">
              <button 
                type="button"
                onClick={handleCreate}
                className="create-btn full"
              >
                <Plus size={14} />
                Create "{searchTerm}"
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SubChannelSelector;
