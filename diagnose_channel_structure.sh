#!/bin/bash
# Channel Directory Diagnostic
# Run this on the oak server to check the channel directory structure

echo "🔍 Channel Directory Diagnostic"
echo "==============================="

BASE_DIR="/var/opt/mimir/mimir-api/channels"

if [ ! -d "$BASE_DIR" ]; then
    echo "❌ Base directory does not exist: $BASE_DIR"
    exit 1
fi

echo "📂 Listing channels directory structure:"
echo "Base: $BASE_DIR"
echo ""

# List all items in channels directory
echo "📁 Top-level items in channels directory:"
ls -la "$BASE_DIR"

echo ""
echo "🔍 Detailed breakdown:"

for item in "$BASE_DIR"/*; do
    if [ -e "$item" ]; then
        basename_item=$(basename "$item")
        if [ -d "$item" ]; then
            echo ""
            echo "📁 Directory: $basename_item"
            echo "   Full path: $item"
            
            # Check for config.json
            if [ -f "$item/config.json" ]; then
                echo "   ✅ Has config.json"
                # Show config ID if possible
                config_id=$(grep -o '"id"[[:space:]]*:[[:space:]]*"[^"]*"' "$item/config.json" 2>/dev/null | cut -d'"' -f4)
                if [ -n "$config_id" ]; then
                    echo "   🆔 Config ID: $config_id"
                fi
            else
                echo "   ❌ No config.json"
            fi
            
            # Check for subdirectories
            subdirs=$(find "$item" -maxdepth 1 -type d ! -path "$item" | wc -l)
            if [ $subdirs -gt 0 ]; then
                echo "   📂 Subdirectories:"
                find "$item" -maxdepth 1 -type d ! -path "$item" -exec basename {} \; | sed 's/^/      - /'
            fi
        else
            echo ""
            echo "📄 File: $basename_item"
            echo "   Full path: $item"
        fi
    fi
done

echo ""
echo "🚫 Checking for weird directory names or spacing issues:"

# Look for directories with unusual characters
find "$BASE_DIR" -maxdepth 1 -type d -name "*frame*" -exec ls -la {} \;

echo ""
echo "🔍 Checking for hidden directories or files:"
ls -la "$BASE_DIR" | grep "^\."

echo ""
echo "💡 Summary:"
echo "=========="

valid_channels=0
invalid_dirs=0

for item in "$BASE_DIR"/*; do
    if [ -d "$item" ]; then
        basename_item=$(basename "$item")
        if [ -f "$item/config.json" ]; then
            ((valid_channels++))
            echo "   ✅ Valid channel: $basename_item"
        else
            ((invalid_dirs++))
            echo "   ❌ Directory without config: $basename_item"
        fi
    fi
done

echo ""
echo "📊 Totals:"
echo "   Valid channels: $valid_channels"
echo "   Invalid directories: $invalid_dirs"

if [ $invalid_dirs -gt 0 ]; then
    echo ""
    echo "💡 The invalid directories might be causing the discovery warnings."
    echo "   Consider removing or moving directories that aren't proper channels."
fi
