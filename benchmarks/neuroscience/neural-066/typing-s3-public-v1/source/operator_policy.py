"""Closed operator-only membership policy; no private policy values bundled.

This is a public derivative boundary, not policy approval. The actual policy
must be authenticated against a separately reviewed root authority before data.
No defaults, discovery, environment variables or scientific execution here.
"""
from core import need
from safe_io import capture, child, strict

SCHEMA = 'neural066_operator_membership_policy_v1'
FIELDS = {'schema', 'task', 'source_revision', 'loader_revision', 'asset_pins',
          'meg_aliases', 'exclusions', 'drop_empty_keys'}

def descriptor(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'},
         'Required exact operator policy artifact pin')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= 33554432,
         'Finite original operator policy artifact extent')
    need(type(value['sha256']) is str and len(value['sha256']) == 64 and
         all(c in '0123456789abcdef' for c in value['sha256']),
         'Exact operator policy artifact digest')
    return value

def validate(value):
    need(type(value) is dict and set(value) == FIELDS,
         'Required closed operator membership policy; no defaults')
    need(value['schema'] == SCHEMA and value['task'] == 'NEURAL-066' and
         value['drop_empty_keys'] is True, 'Original policy identity and empty disposition')
    need(value['source_revision'] == '88f9096c6ce3a3fb17cc7b8e3131ff7f96da5684' and
         value['loader_revision'] == '5f9889621d0df391c5aab37c996683d308e6e926',
         'Original selected source revisions')
    need(type(value['asset_pins']) is dict and
         set(value['asset_pins']) == {'cohort', 'logs', 'loader'},
         'All exact original cohort, log and loader pins')
    for d in value['asset_pins'].values():
        descriptor(d)
    aliases = value['meg_aliases']
    need(type(aliases) is dict and len(aliases) == 4 and
         all(type(k) is str and k and type(v) is str and v for k,v in aliases.items()),
         'Complete original four-entry modality-local alias policy')
    exclusions = value['exclusions']
    need(type(exclusions) is list and len(exclusions) == 1,
         'Exactly one original nonempty endpoint exclusion')
    for row in exclusions:
        need(type(row) is dict and set(row) == {'modality','alias','session','task','trial'},
             'Closed original exclusion identity')
        need(row['modality'] == 'MEG' and type(row['alias']) is str and row['alias'] and
             type(row['task']) is str and row['task'] and
             type(row['session']) is int and row['session'] > 0 and
             type(row['trial']) is int and row['trial'] > 0,
             'Typed original exclusion; no fabricated default identity')
    return value

def load(root, selected, expected, cap):
    need(type(selected) is dict and set(selected) == {'path','bytes','sha256'},
         'Required operator membership policy descriptor is absent or invalid')
    descriptor(expected)
    need({k:selected[k] for k in ('bytes','sha256')} == expected,
         'Operator policy differs from independently reviewed selection')
    need(type(cap) is int and 0 < selected['bytes'] <= cap,
         'Operator policy exceeds original metadata allowance')
    return validate(strict(capture(child(root, selected['path']), cap, expected)))

def eligible(row, policy):
    # Policy was independently authenticated/validated by the owning caller.
    return bool(row['keys']) and not any(
        all(row[k] == exclusion[k] for k in ('modality','alias','session','task','trial'))
        for exclusion in policy['exclusions'])
