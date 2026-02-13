#!/usr/bin/env bash
# scripts/functions/convert.sh — Run fn-convert for each article in kb/staging/
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGING_DIR="$REPO_ROOT/kb/staging"
SERVING_DIR="$REPO_ROOT/kb/serving"

if [ ! -d "$STAGING_DIR" ] || [ -z "$(ls -A "$STAGING_DIR" 2>/dev/null)" ]; then
    echo "No articles found in kb/staging/. Add article folders first."
    exit 1
fi

# Ensure serving directory exists
mkdir -p "$SERVING_DIR"

for article_dir in "$STAGING_DIR"/*/; do
    article_id="$(basename "$article_dir")"
    echo ""
    echo "=== fn-convert: $article_id ==="
    output_dir="$SERVING_DIR/$article_id"
    mkdir -p "$output_dir"
    (cd "$REPO_ROOT/src/functions" && uv run python -m fn_convert "$article_dir" "$output_dir")
done

echo ""
echo "Done. Processed articles are in kb/serving/."
