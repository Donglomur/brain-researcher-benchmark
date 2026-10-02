#!/bin/bash
set -euo pipefail
SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SOLUTION_DIR/compute.py" "$@"
