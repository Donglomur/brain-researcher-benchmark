"""Typed construction and streaming of operator-captured observations.

Original MAT/pickle/NWB extraction is a separately source-bound native recipe.
No arbitrary pickle loader exists. These constructors preserve clock/row joins;
they cannot establish original schema, memberships or warp equivalence by fiat.
"""
import hashlib
import os
import stat
from pathlib import Path
from .validation import exact, need, ident, integer, finite, vector, descriptor, decode, encoded, digest


def construct_rows(observations, columns, clock, role, expected_ids):
    """Concrete neutral column/identity constructor after source extraction.

    columns maps exact source names; no inferred axis, scaling or missing fill.
    All scientific transformations must already have an admitted recipe/output.
    """
    need(role in ('train', 'history', 'query', 'target', 'analysis'), 'explicit row role')
    ident(clock)
    need(type(columns) is dict and columns and type(expected_ids) is list and
         len(set(expected_ids)) == len(expected_ids), 'exact source columns and ordered support')
    iterator = iter(observations)
    for expected in expected_ids:
        ident(expected)
        raw = next(iterator, None)
        need(type(raw) is dict and set(raw) == {'sample_id', 'tick', *columns.values()}, 'source schema exact')
        need(raw['sample_id'] == expected, 'original ordered sample identity')
        row = {'sample_id': expected, 'clock': clock, 'tick': integer(raw['tick'])}
        for public_name, native_name in columns.items():
            ident(public_name)
            row[public_name] = raw[native_name]
        validate_row(role, row)
        yield row
    need(next(iterator, None) is None, 'no undeclared source observations')


def validate_row(role, row):
    fields = {
        'train': ('sample_id', 'clock', 'tick', 'neural', 'behavior', 'auxiliary', 'condition'),
        'history': ('sample_id', 'clock', 'tick', 'neural'),
        'query': ('sample_id', 'clock', 'tick', 'neural'),
        'target': ('sample_id', 'clock', 'tick', 'truth'),
        'analysis': ('sample_id', 'clock', 'tick', 'values'),
    }
    need(role in fields, 'row role')
    exact(row, fields[role], 'typed observation')
    ident(row['sample_id']); ident(row['clock']); integer(row['tick'])
    if 'neural' in row:
        for x in vector(row['neural']):
            integer(x, 0)  # Authentic neural counts; rates use explicit analysis records.
    for name in ('behavior', 'auxiliary', 'truth', 'values'):
        if name in row:
            vector(row[name])
    if 'condition' in row:
        need(row['condition'] is None or type(row['condition']) in (str, int), 'training condition identity')
    return row


def write_constructed(root, relative, rows, role, maximum):
    """Exclusive operator artifact; never overwrite original observations."""
    root = Path(root)
    descriptor({'path': relative, 'bytes': 0, 'sha256': '0' * 64})
    path = root / relative
    need(root.is_absolute() and path.parent.is_dir() and
         all(not p.is_symlink() for p in (path, *path.parents)), 'owned regular output path')
    h, count, total = hashlib.sha256(), 0, 0
    with path.open('xb') as stream:
        for row in rows:
            validate_row(role, row)
            raw = encoded(row) + b'\n'
            total += len(raw)
            need(total <= maximum, 'constructor output ceiling')
            stream.write(raw); h.update(raw); count += 1
        stream.flush(); os.fsync(stream.fileno())
    return {'descriptor': {'path': relative, 'bytes': total, 'sha256': h.hexdigest()},
            'rows': count, 'role': role, 'scientific_authentication': False}


class PacketStore:
    def __init__(self, root, index, admission):
        admission.recheck()
        exact(index, ('schema', 'case', 'source_clock', 'streams', 'original_extraction_sha256', 'output_schema','experiment','construction'), 'data index')
        need(index['schema'] == 'motormint_source_rows_v2', 'typed original source-row index')
        case = next((c for c in admission.plan['cases'] if c['id'] == index['case']), None)
        need(case is not None and digest(index) == case['input_index_sha256'], 'precommitted exact data index')
        from .validation import sha
        sha(index['original_extraction_sha256']); ident(index['source_clock'])
        schema = index['output_schema']
        exact(schema, ('width', 'target_columns', 'training_rates_required'), 'public output geometry')
        integer(schema['width'], 1, 1000000)
        need(type(schema['target_columns']) is list and schema['target_columns'] and
             len(set(schema['target_columns'])) == len(schema['target_columns']), 'ordered private-target projection')
        for column in schema['target_columns']:
            integer(column, 0, schema['width'] - 1)
        need(type(schema['training_rates_required']) is bool and
             schema['training_rates_required'] is (case['mode'] == 'neural_acausal'), 'NLB train/test rate obligation')
        need(type(index['streams']) is list and index['streams'], 'nonempty typed stream index')
        names = set()
        for stream in index['streams']:
            exact(stream, ('id', 'role', 'trial', 'descriptor', 'rows', 'first_tick', 'step', 'width'), 'stream')
            ident(stream['id']); ident(stream['trial']); descriptor(stream['descriptor'])
            need(stream['id'] not in names and stream['role'] in ('train', 'history', 'query', 'target', 'analysis'), 'unique stream/role')
            names.add(stream['id'])
            integer(stream['rows'], 1); integer(stream['first_tick']); integer(stream['step'], 1)
            integer(stream['width'], 1, 1000000)
            if stream['role'] == 'target':
                need(stream['width'] == len(schema['target_columns']), 'target projection support')
        # No public neural training interval may intersect a query interval.
        train = [s for s in index['streams'] if s['role'] == 'train']
        query = [s for s in index['streams'] if s['role'] == 'query']
        for a in train:
            for b in query:
                need(a['first_tick'] + a['rows'] * a['step'] <= b['first_tick'] or
                     b['first_tick'] + b['rows'] * b['step'] <= a['first_tick'], 'training/query source-clock exclusion')
        ordered = sorted(query, key=lambda s: s['first_tick'])
        for a, b in zip(ordered, ordered[1:]):
            need(a['first_tick'] + a['rows'] * a['step'] <= b['first_tick'], 'nonoverlapping chronological queries')
        for b in query:
            histories = [a for a in index['streams'] if a['role'] == 'history' and a['trial'] == b['trial']]
            need(len(histories) <= 1, 'one explicit contiguous history prefix')
            if histories:
                a = histories[0]
                need(a['step'] == b['step'] and a['first_tick'] + a['rows'] * a['step'] == b['first_tick'], 'prefix ends at current query')
            targets = [a for a in index['streams'] if a['role'] == 'target' and a['trial'] == b['trial']]
            need(len(targets) == 1 and all(targets[0][k] == b[k] for k in ('first_tick', 'rows', 'step')), 'complete private target support')
        self.root, self.index, self.case, self.admission = Path(root), index, case, admission
        self.commitment = digest(index)

    def streams(self, role):
        return sorted((s for s in self.index['streams'] if s['role'] == role), key=lambda s: (s['first_tick'], s['id']))

    def rows(self, stream):
        """Two-pass authenticated JSONL read; no unbounded original array load."""
        self.admission.recheck()
        need(digest(self.index) == self.commitment and stream in self.index['streams'], 'frozen stream membership')
        desc = stream['descriptor']; path = self.root / desc['path']
        cap = self.admission.value['limits']['file_bytes']
        need(desc['bytes'] <= cap and self.root.is_absolute() and
             all(not p.is_symlink() for p in (path, *path.parents)), 'owned bounded captured data')
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as handle:
            before = os.fstat(handle.fileno())
            need(stat.S_ISREG(before.st_mode) and before.st_size == desc['bytes'], 'exact source extent')
            h, total = hashlib.sha256(), 0
            for block in iter(lambda: handle.read(65536), b''):
                total += len(block); need(total <= cap, 'data input ceiling'); h.update(block)
            need(total == desc['bytes'] and h.hexdigest() == desc['sha256'], 'source bytes before release')
            handle.seek(0); h, count, seen = hashlib.sha256(), 0, set()
            while True:
                raw = handle.readline(self.admission.value['limits']['frame_bytes'] + 1)
                if not raw:
                    break
                need(len(raw) <= self.admission.value['limits']['frame_bytes'] and raw.endswith(b'\n'), 'bounded complete data row')
                h.update(raw); row = validate_row(stream['role'], decode(raw))
                need(row['clock'] == self.index['source_clock'] and
                     row['tick'] == stream['first_tick'] + count * stream['step'], 'source clock/tick identity')
                need(row['sample_id'] not in seen, 'unique original row IDs')
                seen.add(row['sample_id'])
                field = {'target': 'truth', 'analysis': 'values'}.get(stream['role'], 'neural')
                need(len(row[field]) == stream['width'], 'exact original channel order/width')
                count += 1; need(count <= stream['rows'], 'no extra stream rows')
                if self.case['module']=='neuron_loss' and self.case['factors']['regime']=='undetected' and stream['role'] in ('query','history'):
                    retained=set(self.index['construction']['selected_channels'])
                    need(all(value==0 for j,value in enumerate(row['neural']) if j not in retained), 'undetected loss actually zeros removed test channels')
                yield row
            after = os.fstat(handle.fileno())
            need(count == stream['rows'] and h.hexdigest() == desc['sha256'], 'complete stable consumed stream')
            need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                 (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'capture unchanged during release')


def constructed_index_identity(case,index,selected_channels,raw_channel_count):
    """Seal actual extraction/construction metadata before packet hashing.

    Callers supply independently authenticated raw source/masks. This helper
    does not claim that metadata alone proves original extraction provenance.
    """
    from .bindings import experiment
    result=dict(index,experiment=experiment(case),construction={'source_recipe_sha256':case['source_recipe_sha256'],'experiment_sha256':digest(experiment(case)),'selected_channels':selected_channels,'raw_channel_count':raw_channel_count})
    return result
