import React, { useState } from 'react';
import { 
  BarChart3, TrendingUp, TrendingDown, Users, Image, 
  Clock, Calendar, Eye, Activity, RefreshCw, Filter
} from 'lucide-react';
import './SubChannelStats.css';

const SubChannelStats = ({
  subChannelId,
  stats = {},
  timeRange = '7d', // 1d, 7d, 30d, 90d
  onTimeRangeChange,
  showDetailedMetrics = true,
  showComparisons = true,
  showCharts = false,
  loading = false,
  className = ""
}) => {
  const [selectedMetric, setSelectedMetric] = useState('views');
  const [viewMode, setViewMode] = useState('summary'); // summary, detailed, charts

  const {
    totalContent = 0,
    totalViews = 0,
    uniqueViews = 0,
    totalEngagement = 0,
    averageViewTime = 0,
    contentByType = {},
    viewsByPeriod = [],
    topContent = [],
    recentActivity = [],
    performance = {},
    comparisons = {}
  } = stats;

  const timeRangeOptions = [
    { value: '1d', label: 'Last 24 hours' },
    { value: '7d', label: 'Last 7 days' },
    { value: '30d', label: 'Last 30 days' },
    { value: '90d', label: 'Last 90 days' }
  ];

  const metricOptions = [
    { value: 'views', label: 'Views', icon: Eye },
    { value: 'engagement', label: 'Engagement', icon: Activity },
    { value: 'content', label: 'Content', icon: Image },
    { value: 'performance', label: 'Performance', icon: TrendingUp }
  ];

  const formatNumber = (num) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  const formatDuration = (seconds) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  const getChangeIndicator = (current, previous) => {
    if (!previous || previous === 0) return null;
    const change = ((current - previous) / previous) * 100;
    const isPositive = change > 0;
    
    return (
      <span className={`change-indicator ${isPositive ? 'positive' : 'negative'}`}>
        {isPositive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
        {Math.abs(change).toFixed(1)}%
      </span>
    );
  };

  const renderSummaryStats = () => (
    <div className="stats-grid">
      <div className="stat-card primary">
        <div className="stat-icon">
          <Image size={20} />
        </div>
        <div className="stat-content">
          <div className="stat-value">{formatNumber(totalContent)}</div>
          <div className="stat-label">Total Content</div>
          {showComparisons && comparisons.content && 
            getChangeIndicator(totalContent, comparisons.content.previous)
          }
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-icon">
          <Eye size={20} />
        </div>
        <div className="stat-content">
          <div className="stat-value">{formatNumber(totalViews)}</div>
          <div className="stat-label">Total Views</div>
          {showComparisons && comparisons.views && 
            getChangeIndicator(totalViews, comparisons.views.previous)
          }
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-icon">
          <Users size={20} />
        </div>
        <div className="stat-content">
          <div className="stat-value">{formatNumber(uniqueViews)}</div>
          <div className="stat-label">Unique Views</div>
          {showComparisons && comparisons.uniqueViews && 
            getChangeIndicator(uniqueViews, comparisons.uniqueViews.previous)
          }
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-icon">
          <Activity size={20} />
        </div>
        <div className="stat-content">
          <div className="stat-value">{formatNumber(totalEngagement)}</div>
          <div className="stat-label">Engagement</div>
          {showComparisons && comparisons.engagement && 
            getChangeIndicator(totalEngagement, comparisons.engagement.previous)
          }
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-icon">
          <Clock size={20} />
        </div>
        <div className="stat-content">
          <div className="stat-value">{formatDuration(averageViewTime)}</div>
          <div className="stat-label">Avg. View Time</div>
          {showComparisons && comparisons.averageViewTime && 
            getChangeIndicator(averageViewTime, comparisons.averageViewTime.previous)
          }
        </div>
      </div>

      {performance.score && (
        <div className="stat-card performance">
          <div className="stat-icon">
            <BarChart3 size={20} />
          </div>
          <div className="stat-content">
            <div className="stat-value">{performance.score}%</div>
            <div className="stat-label">Performance Score</div>
            {showComparisons && comparisons.performance && 
              getChangeIndicator(performance.score, comparisons.performance.previous)
            }
          </div>
        </div>
      )}
    </div>
  );

  const renderDetailedMetrics = () => (
    <div className="detailed-metrics">
      {/* Content Breakdown */}
      {Object.keys(contentByType).length > 0 && (
        <div className="metric-section">
          <h4>Content by Type</h4>
          <div className="content-breakdown">
            {Object.entries(contentByType).map(([type, count]) => (
              <div key={type} className="breakdown-item">
                <span className="breakdown-label">{type}</span>
                <span className="breakdown-value">{count}</span>
                <div className="breakdown-bar">
                  <div 
                    className="breakdown-fill" 
                    style={{ width: `${(count / totalContent) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Content */}
      {topContent.length > 0 && (
        <div className="metric-section">
          <h4>Top Performing Content</h4>
          <div className="top-content-list">
            {topContent.slice(0, 5).map((content, index) => (
              <div key={content.id} className="top-content-item">
                <div className="content-rank">#{index + 1}</div>
                <div className="content-info">
                  <div className="content-name">{content.name}</div>
                  <div className="content-stats">
                    {content.views} views • {content.engagement} engagements
                  </div>
                </div>
                <div className="content-score">{content.score}%</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Activity */}
      {recentActivity.length > 0 && (
        <div className="metric-section">
          <h4>Recent Activity</h4>
          <div className="activity-list">
            {recentActivity.slice(0, 8).map((activity, index) => (
              <div key={index} className="activity-item">
                <div className="activity-icon">
                  {activity.type === 'view' && <Eye size={14} />}
                  {activity.type === 'content' && <Image size={14} />}
                  {activity.type === 'engagement' && <Activity size={14} />}
                </div>
                <div className="activity-content">
                  <div className="activity-description">{activity.description}</div>
                  <div className="activity-time">{activity.timeAgo}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Performance Metrics */}
      {performance.metrics && (
        <div className="metric-section">
          <h4>Performance Metrics</h4>
          <div className="performance-grid">
            {Object.entries(performance.metrics).map(([key, value]) => (
              <div key={key} className="performance-item">
                <div className="performance-label">{key.replace(/([A-Z])/g, ' $1').toLowerCase()}</div>
                <div className="performance-value">
                  {typeof value === 'number' ? formatNumber(value) : value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  const renderCharts = () => (
    <div className="charts-section">
      {/* Simple chart representation - in real app would use a charting library */}
      {viewsByPeriod.length > 0 && (
        <div className="chart-container">
          <h4>Views Over Time</h4>
          <div className="simple-chart">
            {viewsByPeriod.map((period, index) => (
              <div key={index} className="chart-bar">
                <div 
                  className="bar-fill" 
                  style={{ 
                    height: `${(period.views / Math.max(...viewsByPeriod.map(p => p.views))) * 100}%` 
                  }}
                />
                <div className="bar-label">{period.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className={`subchannel-stats ${loading ? 'loading' : ''} ${className}`}>
      {/* Header */}
      <div className="stats-header">
        <div className="header-left">
          <h3>Sub-Channel Statistics</h3>
          {subChannelId && (
            <span className="subchannel-id">ID: {subChannelId}</span>
          )}
        </div>
        
        <div className="header-controls">
          {/* Time Range Selector */}
          <div className="time-range-selector">
            <Calendar size={16} />
            <select 
              value={timeRange} 
              onChange={(e) => onTimeRangeChange?.(e.target.value)}
            >
              {timeRangeOptions.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {/* View Mode Selector */}
          <div className="view-mode-selector">
            <button
              type="button"
              className={viewMode === 'summary' ? 'active' : ''}
              onClick={() => setViewMode('summary')}
            >
              Summary
            </button>
            {showDetailedMetrics && (
              <button
                type="button"
                className={viewMode === 'detailed' ? 'active' : ''}
                onClick={() => setViewMode('detailed')}
              >
                Detailed
              </button>
            )}
            {showCharts && (
              <button
                type="button"
                className={viewMode === 'charts' ? 'active' : ''}
                onClick={() => setViewMode('charts')}
              >
                Charts
              </button>
            )}
          </div>

          {/* Refresh Button */}
          <button type="button" className="refresh-btn" disabled={loading}>
            <RefreshCw size={16} className={loading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="stats-loading">
          <RefreshCw size={24} className="spinning" />
          <span>Loading statistics...</span>
        </div>
      )}

      {/* Content */}
      {!loading && (
        <div className="stats-content">
          {viewMode === 'summary' && renderSummaryStats()}
          {viewMode === 'detailed' && showDetailedMetrics && renderDetailedMetrics()}
          {viewMode === 'charts' && showCharts && renderCharts()}
        </div>
      )}

      {/* Metric Selector for Detailed View */}
      {viewMode === 'detailed' && showDetailedMetrics && (
        <div className="metric-selector">
          <Filter size={16} />
          <select 
            value={selectedMetric} 
            onChange={(e) => setSelectedMetric(e.target.value)}
          >
            {metricOptions.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
};

export default SubChannelStats;
