#!/usr/bin/env bash
# scripts/functions/index.sh — Run fn-index for each article in kb/serving/
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SERVING_DIR="$REPO_ROOT/kb/serving"

if [ ! -d "$SERVING_DIR" ] || [ -z "$(ls -A "$SERVING_DIR" 2>/dev/null)" ]; then
    echo "No articles found in kb/serving/. Run 'make convert' first."
    exit 1
fi

for dept_dir in "$SERVING_DIR"/*/; do
    department="$(basename "$dept_dir")"
    for article_dir in "$dept_dir"*/; do
        article_id="$(basename "$article_dir")"
        echo ""
        echo "=== fn-index: $department/$article_id ==="
        (cd "$REPO_ROOT/src/functions" && uv run python -m fn_index "$article_dir")
    done
done

echo ""
echo "Done. Articles indexed into Azure AI Search."
