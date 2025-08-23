#!/usr/bin/env bash
set -euo pipefail

SRC="${HOME}/code/image-frame-channel-mimir/channels/photo_frame/"
DST="${HOME}/code/mimir-api/api-service/channels/photo_frame/"
UPLOADS_REL="assets/uploads/"
DATA_REL="data/"
CURRENT_REL="current/"

# Full destination paths
UPLOADS_DST="${DST}${UPLOADS_REL}"
DATA_DST="${DST}${DATA_REL}"
CURRENT_DST="${DST}${CURRENT_REL}"

# Ensure destination directories exist
mkdir -p "${DST}" "${UPLOADS_DST}" "${DATA_DST}" "${CURRENT_DST}"

# Check if any user data exists (using your original logic pattern)
user_data_exists=false

# Check uploads
if find "${UPLOADS_DST}" -type f -print -quit | grep -q .; then
  echo "📁 Uploads folder is NOT empty — will preserve existing uploads."
  user_data_exists=true
fi

# Check database/data directory  
if find "${DATA_DST}" -type f -print -quit | grep -q .; then
  echo "📊 Data folder is NOT empty — will preserve existing database and galleries."
  user_data_exists=true
fi

# Check current images
if find "${CURRENT_DST}" -type f -print -quit | grep -q .; then
  echo "🖼️ Current images folder is NOT empty — will preserve existing rendered images."
  user_data_exists=true
fi

if [[ "$user_data_exists" == true ]]; then
  echo "🔒 User data detected — syncing code only and preserving all user data."
  # Sync everything except user data directories; --delete applies to non-excluded paths only
  rsync -a --delete \
    --exclude "${UPLOADS_REL}**" \
    --exclude "${DATA_REL}**" \
    --exclude "${CURRENT_REL}**" \
    "${SRC}" "${DST}"
else
  echo "📦 No user data found — performing full sync including source data."
  # Safe to include everything on first sync
  rsync -a --delete "${SRC}" "${DST}"
fi

echo "🚀 Synced: ${SRC} → ${DST}"
