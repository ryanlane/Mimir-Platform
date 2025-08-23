#!/usr/bin/env bash
set -euo pipefail

SRC="${HOME}/code/image-frame-channel-mimir/channels/photo_frame/"
DST="${HOME}/code/mimir-api/api-service/channels/photo_frame/"

# User data directories to preserve
UPLOADS_REL="assets/uploads/"
DATA_REL="data/"
CURRENT_REL="current/"

# Full paths for checking
UPLOADS_DST="${DST}${UPLOADS_REL}"
DATA_DST="${DST}${DATA_REL}"
CURRENT_DST="${DST}${CURRENT_REL}"

# Ensure destination directories exist
mkdir -p "${DST}" "${UPLOADS_DST}" "${DATA_DST}" "${CURRENT_DST}"

# Check if any user data exists
has_uploads=false
has_data=false
has_current=false

if find "${UPLOADS_DST}" -type f -print -quit | grep -q .; then
  has_uploads=true
fi

if find "${DATA_DST}" -type f -print -quit | grep -q .; then
  has_data=true
fi

if find "${CURRENT_DST}" -type f -print -quit | grep -q .; then
  has_current=true
fi

# Determine sync strategy
if [[ "$has_uploads" == true || "$has_data" == true || "$has_current" == true ]]; then
  echo "🔒 User data detected — preserving existing data and syncing code only."
  echo "   📁 Uploads: $([ "$has_uploads" == true ] && echo "PRESERVED" || echo "empty")"
  echo "   📊 Database/Data: $([ "$has_data" == true ] && echo "PRESERVED" || echo "empty")"
  echo "   🖼️ Current Images: $([ "$has_current" == true ] && echo "PRESERVED" || echo "empty")"
  
  # Sync everything except user data directories
  rsync -a --delete \
    --exclude "${UPLOADS_REL}**" \
    --exclude "${DATA_REL}**" \
    --exclude "${CURRENT_REL}**" \
    "${SRC}" "${DST}"
    
  echo "✅ Code updated, user data preserved"
else
  echo "📦 No existing user data found — performing full sync including source data."
  # Safe to include everything on first sync
  rsync -a --delete "${SRC}" "${DST}"
  echo "✅ Full sync completed"
fi

echo "🚀 Synced: ${SRC} → ${DST}"

# Show what was preserved/synced
echo ""
echo "📋 Status Summary:"
echo "   Code Files: UPDATED"
echo "   User Uploads: $([ "$has_uploads" == true ] && echo "PRESERVED" || echo "SYNCED")"
echo "   Database/Galleries: $([ "$has_data" == true ] && echo "PRESERVED" || echo "SYNCED")"
echo "   Rendered Images: $([ "$has_current" == true ] && echo "PRESERVED" || echo "SYNCED")"
