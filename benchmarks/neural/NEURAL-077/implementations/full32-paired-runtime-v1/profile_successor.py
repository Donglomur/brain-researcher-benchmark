"""Narrow immutable successor closing the prior evidence-metadata channel.

The existing data-read/runtime policy is unchanged. No permissive fallback is
provided if this narrower metadata set prevents the selected runtime starting.
"""
from __future__ import annotations

import json
from pathlib import Path
import types

RULE = '(allow file-read-metadata)'


def scopes(client):
    path = Path(client)
    if not path.is_absolute():
        raise ValueError('Absolute frozen client path required')
    return ('(literal "/") (subpath "/System") (subpath "/usr") '
            '(subpath "/Library/Frameworks") (literal "/dev/null") '
            '(literal "/dev/urandom") (literal "/dev/random") '
            '(literal ' + json.dumps(str(path)) + ')')


def successor_profile(base, client):
    """Change only the one global metadata rule of the pinned predecessor."""
    if not isinstance(base, str) or base.count(RULE) != 1:
        raise ValueError('Exactly one predecessor global metadata rule required')
    permitted = scopes(client)
    expected_data = '(allow file-read-data ' + permitted + ')'
    if not base.endswith(expected_data) or base.count('(allow file-read-data ') != 1:
        raise ValueError('Unchanged exact predecessor data-read scope required')
    if '(deny default)' not in base or '(deny sysctl* process-info* network* process-fork)' not in base:
        raise ValueError('Existing default/network/fork denial required')
    replacement = '(allow file-read-metadata ' + permitted + ' (literal "/Library"))'
    result = base.replace(RULE, replacement, 1)
    if RULE in result or result.replace(replacement, RULE, 1) != base:
        raise ValueError('Only the selected metadata rule may change')
    return result


def wrap_wire(wire):
    """Use unchanged framing; only profile construction is replaced."""
    return types.SimpleNamespace(
        WireFailure=wire.WireFailure, read_frame=wire.read_frame,
        write_frame=wire.write_frame,
        sandbox_profile=lambda client: successor_profile(wire.sandbox_profile(client), client),
    )
