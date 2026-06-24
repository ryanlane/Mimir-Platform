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
