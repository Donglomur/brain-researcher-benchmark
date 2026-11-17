"""Trusted operator CLI for the recovered NEURAL-087 binary scorer.

This consumes a previously frozen operator binding, not a participant-supplied
roster. It supplies no sandbox and must remain outside participant access.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from contract import COUNTS, VIEWS, need, node_role
from io_utils import capture, decode, write_json
from scorer import grade, roster, validate_submission


def digest(value):
    need(type(value) is str and len(value) == 64
         and all(c in '0123456789abcdef' for c in value), 'Lowercase SHA256 required')
    return value


def validate_role_paths(args):
    """Reject aliases with metadata only, before opening any input body.

    Resolved names include symlinks and relative spelling; samefile also catches
    hardlinks. This assumes a trusted operator freezes paths during execution;
    it is not protection against concurrent hostile filesystem mutation.
    """
    inputs = ('binding', 'roster', 'anatomy', 'joint', 'targets')
    paths = {role: Path(getattr(args, role)) for role in (*inputs, 'output')}
    resolved = {role: path.resolve() for role, path in paths.items()}

    def aliases(left, right):
        if resolved[left] == resolved[right]:
            return True
        try:
            return os.path.samefile(paths[left], paths[right])
        except FileNotFoundError:
            return False

    for role in inputs[:-1]:
        need(not aliases('targets', role), f'Input role alias: targets and {role}')
    for role in inputs:
        need(not aliases('output', role), f'Output role alias: output and {role}')


def load_bound_roster(binding_path, binding_sha256, roster_path):
    raw = capture(binding_path, 65536)
    need(hashlib.sha256(raw).hexdigest() == digest(binding_sha256), 'Frozen binding digest mismatch')
    binding = decode(raw)
    need(type(binding) is dict and binding.get('schema') == 'neural087_prepared_binding_v1'
         and binding.get('task_id') == 'NEURAL-087', 'Exact task binding')
    allowed = {'schema', 'task_id', 'counts', 'query_roster', 'query_targets',
               'public', 'source_packets', 'model_fits', 'scores_computed', 'research_qualified'}
    need(set(binding) <= allowed, 'Unknown binding field; alternative weighting is unsupported')
    counts = binding.get('counts')
    need(type(counts) is dict and set(counts) == set(COUNTS)
         and all(type(counts[k]) is int and counts[k] == n for k, n in COUNTS.items()),
         'Complete historical population counts required')
    for name in ('query_roster', 'query_targets'):
        pin = binding.get(name)
        need(type(pin) is dict and set(pin) == {'bytes', 'sha256'}, 'Exact input descriptor')
        need(type(pin['bytes']) is int and 0 < pin['bytes'] <= 1048576, 'Bounded input bytes')
        digest(pin['sha256'])
    rows = decode(capture(roster_path, 1048576, binding['query_roster']))
    roster(rows)
    need(len(rows) == COUNTS['query'], 'Complete fixed 6691-pair query population')
    need(all(node_role(r['pre_id']) == node_role(r['post_id']) == 2 for r in rows),
         'Both endpoints must belong to inherited query partition')
    return binding, rows


def main(args):
    validate_role_paths(args)
    binding, rows = load_bound_roster(args.binding, args.binding_sha256, args.roster)
    private_calls = 0
    try:
        submissions = {
            VIEWS[0]: decode(capture(args.anatomy, 1048576)),
            VIEWS[1]: decode(capture(args.joint, 1048576)),
        }
        for view in VIEWS:
            validate_submission(rows, submissions[view])
    except (ValueError, OSError, UnicodeError, OverflowError, RecursionError) as error:
        result = {'task_id': 'NEURAL-087', 'status': 'invalid_submission',
                  'reason': str(error), 'primary': None, 'private_loader_calls': 0,
                  'scientific_success': None, 'research_qualified': False}
    else:
        def private():
            nonlocal private_calls
            private_calls += 1
            return decode(capture(args.targets, 1048576, binding['query_targets']))
        result = grade(rows, submissions, private)
        need(private_calls == 1, 'Exactly one protected read')
    result['operator_binding_sha256'] = args.binding_sha256
    result['qualification'] = 'arithmetic_only_not_empirical_source_qualification'
    result['weighting_scope'] = 'unit_pair_weights_within_equal_presynaptic_groups'
    pin = write_json(args.output, result, 4194304)
    print(json.dumps({'status': result['status'], 'result': pin,
                      'private_loader_calls': private_calls}))
    return 2 if result['status'] == 'invalid_submission' else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('binding', 'roster', 'targets', 'anatomy', 'joint', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--binding-sha256', required=True,
                        help='Digest frozen by the operator before participant execution')
    raise SystemExit(main(parser.parse_args()))
