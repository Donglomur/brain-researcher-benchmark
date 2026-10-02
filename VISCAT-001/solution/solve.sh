#!/bin/bash
set -euo pipefail
TASK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$TASK_DIR/solution/compute.py" --output-dir "${OUTPUT_DIR:-/app/output}" "$@"
