"""Minimal successor: bind the explicit cell envelope used by Campaign.one_cell.

The frozen V1 compiler and its original evidence remain unchanged. V1's plan
admission did not notice the missing policy.cell_limits runtime operand.
"""
from plans import (CAMPAIGN_FIELDS, _Metadata, _copy, _keys,
                   build_campaign_plan as build_campaign_plan_v1,
                   build_feature_plan, central_entry_argv, encode_plan)

CELL_FIELDS = ('wall_seconds', 'cpu_seconds', 'read_bytes', 'write_bytes',
               'files', 'model_calls', 'stream_bytes')


def build_campaign_plan(spec, source_context):
    _keys(spec, (*CAMPAIGN_FIELDS, 'cell_limits'))
    value = _copy(spec)
    cell_limits = value.pop('cell_limits')
    _keys(cell_limits, CELL_FIELDS)
    metadata = _Metadata(source_context)
    common = metadata.module('common')
    for name in ('wall_seconds', 'cpu_seconds'):
        common.finite(cell_limits[name], True)
    for name in CELL_FIELDS[2:]:
        common.integer(cell_limits[name], 1)
    plan = build_campaign_plan_v1(value, source_context)
    plan['policy']['cell_limits'] = cell_limits
    # The original runtime intersects these per-cell values with its global
    # envelope; this compiler neither increases that envelope nor invents one.
    contracts = {name: metadata.body('contracts/' + name) for name in (
        'ISOLATION_CONTRACT.json', 'MODE_PERMISSIONS.json', 'REPORT_HIERARCHY.json', 'CONTRASTS.json')}
    metadata.module('plan').admit(plan, metadata.source, contracts)
    encode_plan(plan)
    return plan
