"""Public CLI is inspection only; authentic run entry is operator-selected API."""
import json
import sys
from .catalog import coverage

if len(sys.argv) != 2 or sys.argv[1] != 'inspect':
    raise SystemExit('Usage: python -m mintbench inspect\nAuthentic execution requires the independently admitted campaign.run API.')
print(json.dumps(coverage(), indent=2))
