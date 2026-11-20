"""Operator-only portable scorer. Validate every prediction before target access."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import endpoint


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        endpoint.need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('Nonstandard JSON constant: ' + value)


def read_json(path, cap, expected_sha256=None):
    with Path(path).open('rb') as handle:
        raw = handle.read(cap + 1)
    endpoint.need(len(raw) <= cap, 'Input exceeds bounded byte cap')
    digest = hashlib.sha256(raw).hexdigest()
    endpoint.need(expected_sha256 is None or digest == expected_sha256, 'Input hash mismatch')
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant), digest


def run(support_path, submission_path, target_path, targets_sha256):
    support, support_hash = read_json(support_path, 131072)
    bundle, submission_hash = read_json(submission_path, 6291456)
    predictions = endpoint.validate_all(bundle, support)
    # No target stat/open/hash before complete public validation. No candidate
    # process is executed here; external process isolation remains operator work.
    targets, target_hash = read_json(target_path, 524288, targets_sha256)
    result = endpoint.grade_validated(predictions, support, targets)
    result['input_sha256'] = {'support': support_hash, 'submission': submission_hash, 'targets': target_hash}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--support', required=True)
    parser.add_argument('--submission', required=True)
    parser.add_argument('--targets', required=True)
    parser.add_argument('--targets-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        endpoint.need(len(args.targets_sha256) == 64 and
                      all(char in '0123456789abcdef' for char in args.targets_sha256), 'Exact target SHA-256 required')
        result = run(args.support, args.submission, args.targets, args.targets_sha256)
        raw = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n'
        with Path(args.output).open('x', encoding='utf-8') as handle:
            handle.write(raw)
    except (ValueError, OSError, TypeError, KeyError, OverflowError) as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__, 'error': str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
