#!/bin/bash
# Example rsync command that preserves user data

rsync -av \
  --exclude 'assets/uploads/' \
  --exclude 'data/' \
  --exclude 'current/' \
  SOURCE_DIR/ DEST_DIR/

echo "✅ Code updated, user data preserved"
echo "📁 Preserved: assets/uploads/, data/, current/"
