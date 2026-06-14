import React from 'react';
import './Skeleton.css';

export function Skeleton({ width, height, borderRadius, className, style }) {
  return (
    <span
      className={`skeleton ${className || ''}`}
      style={{ width, height, borderRadius, ...style }}
      aria-hidden="true"
    />
  );
}

export function SkeletonProgramCard() {
  return (
    <div className="skeleton-card" aria-hidden="true">
      <div className="skeleton-card-header">
        <Skeleton width="55%" height={16} />
        <Skeleton width={52} height={20} borderRadius={3} />
      </div>
      <div className="skeleton-card-body">
        <Skeleton width="80%" height={12} />
        <Skeleton width="65%" height={12} />
        <Skeleton width="40%" height={12} />
      </div>
      <div className="skeleton-card-footer">
        <Skeleton width={80} height={28} borderRadius={6} />
        <Skeleton width={64} height={28} borderRadius={6} />
        <Skeleton width={64} height={28} borderRadius={6} />
      </div>
    </div>
  );
}

export function SkeletonSourceCard() {
  return (
    <div className="skeleton-card" aria-hidden="true">
      <div className="skeleton-card-header">
        <Skeleton width="50%" height={16} />
        <Skeleton width={56} height={20} borderRadius={10} />
      </div>
      <div className="skeleton-card-body">
        <Skeleton width="90%" height={12} />
        <Skeleton width="70%" height={12} />
      </div>
      <div className="skeleton-card-footer">
        <Skeleton width={72} height={28} borderRadius={6} />
        <Skeleton width={80} height={28} borderRadius={6} />
      </div>
    </div>
  );
}

export function SkeletonScreenCard() {
  return (
    <div className="skeleton-screen-card" aria-hidden="true">
      <Skeleton className="skeleton-screen-thumbnail" />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Skeleton width="50%" height={14} />
        <Skeleton width={18} height={18} borderRadius="50%" />
      </div>
      <Skeleton width="70%" height={12} />
      <div style={{ display: 'flex', gap: 8, paddingTop: 4 }}>
        <Skeleton width={72} height={28} borderRadius={6} />
        <Skeleton width={88} height={28} borderRadius={6} />
      </div>
    </div>
  );
}

export default Skeleton;
