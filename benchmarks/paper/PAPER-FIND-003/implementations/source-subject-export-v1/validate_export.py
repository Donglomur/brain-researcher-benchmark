"""Validate native stage support and transport; never recreate MATLAB statistics."""
from __future__ import annotations
import json
import math
import re
from decimal import Decimal
from pathlib import Path

PHASES = frozenset(('stimulus', 'feedback', 'interval'))
SOURCE = {'revision': 'f143b0b7dca77bf9b09d5c7f39352fc5332c83c0',
          'caller_sha256': '15969cc29b6d7d28d4d4700a044454092149b688c6af9c552314a8cbff2ce6bc',
          'operations': 'Ripple_offline_learning.m:77-101'}
MAX_ROWS = 1_000_000
MAX_BYTES = 64 * 1024 * 1024


class ExportError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise ExportError(message)


def obj(value, keys, label):
    need(type(value) is dict and set(value) == set(keys), label + ': exact fields')


def text(value, label, limit=256):
    need(type(value) is str and 0 < len(value) <= limit and
         not any(c in value for c in ('\x00', '\r', '\n')), label + ': bounded text')
    return value


def integer(value, label, minimum=1):
    need(type(value) is int and minimum <= value <= MAX_ROWS, label + ': bounded integer')
    return value


def scalar(value):
    need(type(value) is dict, 'numeric state object')
    state = value.get('state')
    if state == 'finite':
        obj(value, ('state', 'value'), 'finite number')
        v = value['value']
        need(type(v) in (int, float), 'binary64 number, not boolean')
        try:
            f = float(v)
        except (OverflowError, ValueError) as exc:
            raise ExportError('finite binary64 domain') from exc
        need(math.isfinite(f) and f == v, 'lossless finite binary64 domain')
        return state, f
    obj(value, ('state',), 'nonfinite tag')
    need(state in ('nan', 'positive_infinity', 'negative_infinity'), 'explicit numeric state')
    return (state,)


def values(value):
    obj(value, PHASES, 'native three-phase values')
    return {p: scalar(value[p]) for p in PHASES}


def records(packet, name, keys):
    rows = packet[name]
    need(type(rows) is list and 0 < len(rows) <= MAX_ROWS, name + ': complete bounded rows')
    for i, row in enumerate(rows, 1):
        obj(row, keys, name)
        need(type(row['row_id']) is int and row['row_id'] == i, name + ': original row order')
    return rows


def ids(value, label):
    need(type(value) is list and len(value) <= MAX_ROWS, label + ': index list')
    result = [integer(i, label) for i in value]
    need(len(set(result)) == len(result), label + ': duplicate index')
    return result


def validate_packet(packet):
    """Return support diagnostics, with native numeric correctness unqualified.

    Row IDs identify the supplied native-stage table positions. Declared hashes,
    runtime strings and a consistent packet do not authenticate original inputs.
    """
    obj(packet, ('schema', 'source', 'input_identity', 'runtime', 'channels', 'wide',
                 'subjects', 'performance', 'join', 'joined', 'native_tables'), 'packet')
    need(packet['schema'] == 'ripple-subject-native-export/v1', 'schema')
    need(packet['source'] == SOURCE, 'exact source stage')
    obj(packet['input_identity'], ('learnr_input_sha256', 'performance_input_sha256'), 'input declarations')
    for v in packet['input_identity'].values():
        need(type(v) is str and re.fullmatch('[0-9a-f]{64}', v) is not None, 'declared input SHA256')
    obj(packet['runtime'], ('matlab_version', 'rmoutliers_which', 'grpstats_which', 'nanmean_which'), 'runtime')
    for v in packet['runtime'].values():
        text(v, 'declared runtime', 4096)
    channels = records(packet, 'channels', ('row_id', 'channel', 'phase', 'group_count', 'before', 'after', 'outlier'))
    lookup = {}
    for row in channels:
        c = text(row['channel'], 'channel')
        p = text(row['phase'], 'phase')
        need(p in PHASES and (c, p) not in lookup, 'unique known channel-phase support')
        integer(row['group_count'], 'native channel group count')
        before, after = scalar(row['before']), scalar(row['after'])
        need(type(row['outlier']) is bool, 'logical native outlier mask')
        need(after == ('nan',) if row['outlier'] else after == before,
             'flagged values become NaN; unflagged values unchanged')
        lookup[c, p] = after
    need({p for c, p in lookup} == PHASES, 'explicit all-three-phase adapter domain')
    wide = records(packet, 'wide', ('row_id', 'channel', 'subject', 'values'))
    wide_ids, mapped = set(), set()
    for row in wide:
        c, s = text(row['channel'], 'wide channel'), text(row['subject'], 'derived subject')
        need(c not in wide_ids, 'unique channel-wide row')
        wide_ids.add(c)
        need(s == c.rsplit('_', 1)[-1], 'original greedy underscore suffix mapping')
        mapped.add(s)
        vv = values(row['values'])
        for p in PHASES:
            need(vv[p] == lookup.get((c, p), ('nan',)), 'complete unchanged unstack cells')
    need(wide_ids == {c for c, p in lookup}, 'complete channel-wide support')
    subjects = records(packet, 'subjects', ('row_id', 'subject', 'group_count', 'values'))
    subject_lookup = {}
    for row in subjects:
        s = text(row['subject'], 'native subject')
        need(s not in subject_lookup, 'unique native subject rows')
        integer(row['group_count'], 'native subject group count')
        values(row['values'])  # These means are retained, never recomputed here.
        subject_lookup[s] = row
    need(set(subject_lookup) == mapped, 'complete native subject support')
    performance = records(packet, 'performance', ('row_id', 'subject', 'inference', 'memory'))
    performance_ids, seen_performance = [], set()
    for row in performance:
        s = text(row['subject'], 'performance subject')
        need(s not in seen_performance, 'stable intersection cannot cover duplicate performance rows')
        seen_performance.add(s)
        performance_ids.append(s)
        scalar(row['inference']); scalar(row['memory'])
    obj(packet['join'], ('ia', 'ib', 'excluded_subject_row_ids'), 'stable intersection')
    ia, ib = ids(packet['join']['ia'], 'ia'), ids(packet['join']['ib'], 'ib')
    need(ia == list(range(1, len(performance) + 1)), 'all performance rows in original order')
    need(len(ib) == len(ia) and all(i <= len(subjects) for i in ib), 'native subject intersection support')
    need([subjects[i - 1]['subject'] for i in ib] == performance_ids, 'stable behavior-to-subject join')
    excluded = ids(packet['join']['excluded_subject_row_ids'], 'excluded learned subjects')
    selected = set(ib)
    need(excluded == [i for i in range(1, len(subjects) + 1) if i not in selected], 'explicit extra learned subjects')
    joined = records(packet, 'joined', ('row_id', 'subject_row_id', 'subject', 'values', 'inference', 'memory'))
    need(len(joined) == len(performance), 'complete joined performance rows')
    for n, row in enumerate(joined):
        s, perf = subjects[ib[n] - 1], performance[n]
        need(type(row['subject_row_id']) is int and row['subject_row_id'] == ib[n] and
             row['subject'] == s['subject'] == perf['subject'], 'joined row identities')
        need(values(row['values']) == values(s['values']), 'joined native phase values')
        for k in ('inference', 'memory'):
            need(scalar(row[k]) == scalar(perf[k]), 'exact original behavior assignment')
    tables = packet['native_tables']
    names = ('before', 'after', 'wide', 'subjects', 'performance', 'joined')
    obj(tables, names, 'native table metadata')
    heights = (len(channels), len(channels), len(wide), len(subjects), len(performance), len(joined))
    expected = ({'channel','phase','GroupCount','fun1_trial_ripple'},
                {'channel','phase','GroupCount','fun1_trial_ripple'},
                {'channel'} | PHASES, {'subject','GroupCount'} | PHASES,
                {'subject','testBeforeInfer','testBeforeMemory'},
                {'subject','GroupCount','eleInfer_perf','eleMemory_perf'} | PHASES)
    for name, height, wanted in zip(names, heights, expected):
        meta = tables[name]
        obj(meta, ('columns', 'classes', 'row_names', 'height'), 'native metadata ' + name)
        need(type(meta['height']) is int and meta['height'] == height, 'native table height')
        cols, classes, row_names = meta['columns'], meta['classes'], meta['row_names']
        need(type(cols) is list and 0 < len(cols) <= 256, 'native column identities')
        for c in cols: text(c, 'column name')
        need(len(set(cols)) == len(cols), 'unique native column identities')
        need(wanted <= set(cols) if name == 'performance' else set(cols) == wanted, 'native source columns')
        need(type(classes) is list and len(classes) == len(cols), 'native class roster')
        for c in classes: text(c, 'native class')
        need(type(row_names) is list and len(row_names) in (0, height), 'complete native row names')
        for r in row_names: text(r, 'native row name')
        need(len(set(row_names)) == len(row_names), 'unique native row names')
    need(tables['before'] == tables['after'], 'masking preserves table metadata')
    return {'channel_phase_rows': len(channels), 'channels': len(wide),
            'learned_subjects': len(subjects), 'performance_subjects': len(performance),
            'excluded_learned_subject_rows': excluded,
            'flagged_channel_phase_rows': sum(r['outlier'] for r in channels),
            'native_numeric_correctness': 'not_evaluated', 'input_authenticity': 'not_established',
            'reproduction_qualified': False, 'same_task_improvement_qualified': False}


def load_packet(path):
    """Bounded JSON interchange; native source or scientific arrays are not loaded."""
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    need(0 < len(raw) <= MAX_BYTES, 'bounded JSON packet')
    def pairs(rows):
        result = {}
        for k, v in rows:
            need(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    def floating(v):
        f = float(v)
        need(math.isfinite(f), 'nonfinite JSON exponent')
        need(f != 0 or Decimal(v) == 0, 'nonzero JSON underflow')
        return f
    def constant(v):
        raise ExportError('nonfinite JSON constant')
    return json.loads(raw, object_pairs_hook=pairs, parse_float=floating, parse_constant=constant)


if __name__ == '__main__':
    import sys
    need(len(sys.argv) == 2, 'usage: validate_export.py packet.json')
    print(json.dumps(validate_packet(load_packet(sys.argv[1])), sort_keys=True, allow_nan=False))
