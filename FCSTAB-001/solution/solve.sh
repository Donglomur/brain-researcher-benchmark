#!/bin/bash
set -euo pipefail

# Installed beside compute.py in /solution. Isolated Python deliberately omits
# the script directory; add only this explicit oracle directory before imports.
oracle_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 -I -B -c 'import sys; sys.path.insert(0, sys.argv.pop(1)); import compute; raise SystemExit(compute.main())' "$oracle_dir" "$@"
