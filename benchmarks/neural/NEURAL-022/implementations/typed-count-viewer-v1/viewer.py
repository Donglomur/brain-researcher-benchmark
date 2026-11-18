"""Operator-side count-grid viewer and first-final response collector for NEURAL-022.

Only stdlib is required. This typed protocol is not a participant sandbox, and
its SVG strings are not evidence of image rendering or a model evaluation.
"""
import argparse
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

CONDITION = 'typed_binned_count_grid_v1'
PREDECESSOR = {'bytes': 612, 'sha256': 'b025015f5bb88862e6f8f93337d38177269fb5710b4a91f401014464e52130be'}
PRODUCER = {'bytes': 4998, 'sha256': 'cb3048b3da9231709732209153dd5a46964416452764630361d64ab25196bd7c'}
INSTRUCTION_SHA256 = 'a5cbf1f275fad46c676351b12219fb3d0af3c9433b4baee087b5234273a4e34e'
DIRECTIONS = tuple(range(0, 360, 45))
PUBLIC_CAPS = {'training.npz': 524288, 'queries.npz': 393216, 'cases.json': 16384, 'TASK.md': 16384}
PANEL_CAP = 2 * 1024 * 1024
SVG_CAP = 128 * 1024
REQUEST_CAP = 4096
MAX_ACTIONS = 4096
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
RECEIPT_CAP = 2 * 1024 * 1024
REPRESENTATION = {
    'counts': 'nonnegative_integer_spikes_per_bin', 'axes': ['bin', 'unit'],
    'unit_positions': list(range(65)), 'bin_edges_ms': [0, 20, 40, 60, 80, 100, 120],
    'velocity_units': 'nominal_m/s', 'relative_clock': 'retrospective_movement_onset',
}
INSTRUCTIONS = (
    'Predict nominal mean x/y hand velocity in m/s for all 92 queries. '
    'All 141 active calibration trials are available through view(training,index), '
    'and all 92 query trials through view(query,index). Calibration views include '
    'velocity labels; query views never do. Each grid preserves six 20 ms bins and '
    '65 source-unit positions. Cells are integer spike counts, not within-bin spike '
    'times. Zero is observed zero. Counts are not smoothed or normalized. '
    'Use only these typed views and answer actions; raw numerical analysis, code, '
    'decoder calls, source lookup, target access and score feedback belong outside '
    'this proposed viewer condition. Whether the external participant obeyed these '
    'rules is not certified here. Fit conceptual relations on active calibration '
    'only; no query-based fitting or normalization. Each first valid answer is '
    'final. Finish requires all 92 finite two-component answers. '
    'Viewing calibration or any particular crop is optional and is recorded. '
    'The target uses the same retrospective 120 ms movement-onset window. '
    'This exposed single-session task does not establish online or cross-animal '
    'generalization. Passive reference decoders had extra passive calibration labels.'
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def descriptor(value, cap):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}
         and type(value['bytes']) is int and 0 < value['bytes'] <= cap
         and type(value['sha256']) is str and re.fullmatch('[a-f0-9]{64}', value['sha256']),
         'Exact bounded descriptor')


def capture(path, cap, expected_sha256):
    """Capture only the two named numerical-export files, without following links."""
    need(type(expected_sha256) is str and re.fullmatch('[a-f0-9]{64}', expected_sha256),
         'Operator-selected SHA256')
    path = Path(os.path.abspath(path))
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'No symbolic input path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, 'Bounded ordinary single-link input')
        with os.fdopen(fd, 'rb', closefd=False) as handle:
            raw = handle.read(before.st_size + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        need(len(raw) == before.st_size and all(getattr(before, f) == getattr(after, f) for f in fields),
             'Stable complete input')
        need(hashlib.sha256(raw).hexdigest() == expected_sha256, 'Selected input commitment')
        return raw
    finally:
        os.close(fd)


def validate_export(raw, export_sha256):
    """Bind the exact selected manifest before trusting its observation descriptor."""
    need(type(raw) is bytes and 0 < len(raw) <= 32768, 'Bounded exact export manifest bytes')
    need(type(export_sha256) is str and re.fullmatch('[a-f0-9]{64}', export_sha256)
         and hashlib.sha256(raw).hexdigest() == export_sha256, 'Operator-selected export commitment')
    value = strict(raw)
    fields = {'schema', 'source', 'condition', 'packet', 'packet_producer', 'public_inputs',
              'observation', 'training_rows', 'query_rows', 'count_values', 'training_velocity_values',
              'provider_delivery_qualified', 'authenticity_requires_external_packet_custody'}
    need(type(value) is dict and set(value) == fields
         and value['schema'] == 'neural022_numerical_export_v1'
         and value['source'] == PREDECESSOR and value['packet_producer'] == PRODUCER
         and value['condition'] == 'direct_numerical_full_panel_v1'
         and type(value['training_rows']) is int and value['training_rows'] == 141
         and type(value['query_rows']) is int and value['query_rows'] == 92
         and type(value['count_values']) is int and value['count_values'] == 90870
         and type(value['training_velocity_values']) is int and value['training_velocity_values'] == 282
         and value['provider_delivery_qualified'] is False
         and value['authenticity_requires_external_packet_custody'] is True,
         'Exact predecessor export; no readiness inheritance')
    descriptor(value['packet'], 32768)
    need(type(value['public_inputs']) is dict and set(value['public_inputs']) == set(PUBLIC_CAPS),
         'Exactly the original public inputs')
    for name, cap in PUBLIC_CAPS.items():
        descriptor(value['public_inputs'][name], cap)
    descriptor(value['observation'], PANEL_CAP)
    return value


def load_export(root, export_sha256):
    """Return bound observation/manifest bytes; no array or private-file reads."""
    root = Path(root)
    raw = capture(root / 'EXPORT.json', 32768, export_sha256)
    value = validate_export(raw, export_sha256)
    observation = capture(root / 'OBSERVATION.json', PANEL_CAP, value['observation']['sha256'])
    need(pin(observation) == value['observation'], 'Exact complete observation extent')
    return observation, raw


def finite_pair(value):
    try:
        return type(value) is list and len(value) == 2 and all(
            type(x) in (float, int) and math.isfinite(x) for x in value)
    except OverflowError:
        return False


def validate_panel(raw):
    need(type(raw) is bytes and 0 < len(raw) <= PANEL_CAP, 'Bounded complete numerical panel')
    value = strict(raw)
    need(type(value) is dict and set(value) == {'schema', 'task_id', 'condition', 'instructions',
         'original_public_scientific_contract', 'representation', 'training', 'queries'}
         and value['schema'] == 'neural022_numerical_observation_v1'
         and value['task_id'] == 'NEURAL-022' and value['condition'] == 'direct_numerical_full_panel_v1'
         and type(value['instructions']) is str
         and hashlib.sha256(value['instructions'].encode()).hexdigest() == INSTRUCTION_SHA256
         and encoded(value['representation']) == encoded(REPRESENTATION)
         and type(value['original_public_scientific_contract']) is str
         and len(value['original_public_scientific_contract'].encode()) <= 16384,
         'Original complete count representation and instruction binding')
    ids = set()
    for key, number in (('training', 141), ('queries', 92)):
        rows = value[key]
        need(type(rows) is list and len(rows) == number, 'Complete calibration/query denominator')
        for row in rows:
            fields = {'id', 'direction', 'counts', 'velocity'} if key == 'training' else {'id', 'mode', 'direction', 'counts'}
            need(type(row) is dict and set(row) == fields and type(row['id']) is str
                 and re.fullmatch('[a-f0-9]{24}', row['id']) and row['id'] not in ids
                 and type(row['direction']) is int and row['direction'] in DIRECTIONS,
                 'Opaque distinct identities and exact public fields')
            ids.add(row['id'])
            counts = row['counts']
            need(type(counts) is list and len(counts) == 6 and all(type(b) is list and len(b) == 65
                 and all(type(c) is int and 0 <= c <= 2**63-1 for c in b) for b in counts),
                 'Exact six-bin/65-unit nonnegative int64 counts')
            if key == 'training':
                need(finite_pair(row['velocity']) and all(type(x) is float for x in row['velocity']),
                     'Finite float64-derived calibration velocity')
            else:
                need(row['mode'] in ('active', 'passive'), 'Original query mode')
        need({r['direction'] for r in rows} == set(DIRECTIONS), 'All eight directions')
    for mode, number in (('passive', 40), ('active', 52)):
        rows = [r for r in value['queries'] if r['mode'] == mode]
        need(len(rows) == number and {r['direction'] for r in rows} == set(DIRECTIONS),
             'Complete mode-direction support')
    return value


def interval(value, upper):
    need(type(value) is list and len(value) == 2 and all(type(x) is int for x in value)
         and 0 <= value[0] < value[1] <= upper, 'Bounded half-open integer crop')
    return value


def grid(row, split, index, units, bins):
    """Every selected count remains an exact decimal text cell; no spike-time invention."""
    u0, u1 = interval(units, 65); b0, b1 = interval(bins, 6)
    width, height = max(1000, 110 + 180*(b1-b0)), 115 + 24*(u1-u0)
    mode = 'active calibration' if split == 'training' else row['mode'] + ' query'
    title = f'{mode} {index}; id {row["id"]}; direction {row["direction"]} degrees'
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<g fill="black" font-family="monospace" font-size="12">',
             f'<text x="10" y="18">{html.escape(title)}</text>',
             '<text x="10" y="38">Integer counts; bins in ms from retrospective movement onset.</text>']
    if split == 'training':
        lines.append(f'<text x="10" y="58">Calibration velocity x,y (nominal m/s): {html.escape(repr(row["velocity"]))}</text>')
    for b in range(b0, b1):
        lines.append(f'<text x="{100+180*(b-b0)}" y="84">[{b*20},{(b+1)*20}) ms</text>')
    for u in range(u0, u1):
        y = 108 + 24*(u-u0)
        lines.append(f'<text x="10" y="{y}">unit {u}</text>')
        for b in range(b0, b1):
            lines.append(f'<text x="{100+180*(b-b0)}" y="{y}" data-bin="{b}" data-unit="{u}">{row["counts"][b][u]}</text>')
    lines.extend(['</g>', '</svg>'])
    svg = '\n'.join(lines)
    need(len(svg.encode()) <= SVG_CAP, 'Bounded exact SVG without truncation')
    return svg


class Session:
    """Trusted operator state; do not expose this object or source files to participants."""
    def __init__(self, observation, export_manifest, export_sha256, *, action_limit=MAX_ACTIONS, output_limit=MAX_OUTPUT_BYTES):
        bound = validate_export(export_manifest, export_sha256)
        need(type(observation) is bytes and 0 < len(observation) <= PANEL_CAP,
             'Bounded observation before binding hash')
        need(pin(observation) == bound['observation'], 'Observation belongs to exact selected export')
        need(type(action_limit) is int and 327 <= action_limit <= MAX_ACTIONS,
             'Action allowance includes about, 233 views, 92 answers and finish')
        need(type(output_limit) is int and 12*1024*1024 <= output_limit <= MAX_OUTPUT_BYTES,
             'Complete-view allowance; external session budget must be frozen')
        self._panel = validate_panel(observation)
        self._observation = pin(observation); self._export = pin(export_manifest)
        self._answers = {}; self._views = []; self._events = []
        self._action_limit = action_limit; self._output_limit = output_limit
        self._bytes = 0; self._attempts = 0; self._closed = False
        self._chain = '0'*64

    def _dispatch(self, request):
        need(type(request) is dict and type(request.get('action')) is str, 'Typed action object')
        action = request['action']
        if action == 'about':
            need(set(request) == {'action'}, 'Exact about action')
            return {'condition': CONDITION, 'instructions': INSTRUCTIONS,
                    'training_examples': 141, 'queries': 92, 'representation': REPRESENTATION,
                    'original_public_scientific_contract': self._panel['original_public_scientific_contract'],
                    'action_limit': self._action_limit, 'output_limit_bytes': self._output_limit,
                    'external_isolation_verified': False, 'image_rendering_verified': False}
        if action == 'view':
            need(set(request) == {'action', 'split', 'index', 'units', 'bins'}
                 and request['split'] in ('training', 'query'), 'Exact typed view action')
            split = request['split']; rows = self._panel['training' if split == 'training' else 'queries']
            index = request['index']
            need(type(index) is int and 0 <= index < len(rows), 'Exact available row index')
            svg = grid(rows[index], split, index, request['units'], request['bins'])
            return {'media_type': 'image/svg+xml', 'svg': svg, 'split': split, 'index': index,
                    'units': list(request['units']), 'bins': list(request['bins'])}
        if action == 'answer':
            need(set(request) == {'action', 'index', 'velocity'} and type(request['index']) is int
                 and 0 <= request['index'] < 92 and finite_pair(request['velocity']),
                 'One query index and two finite nonboolean velocities')
            need(request['index'] not in self._answers, 'First accepted answer is final')
            return {'accepted': True, 'index': request['index'], 'answers_after_acceptance': len(self._answers)+1}
        if action == 'finish':
            need(set(request) == {'action'} and len(self._answers) == 92, 'Complete92 before finish')
            return {'schema': 'neural022_predictions_v1', 'predictions': [
                {'id': row['id'], 'velocity': self._answers[i]} for i, row in enumerate(self._panel['queries'])]}
        raise ValueError('Unknown typed action')

    def apply(self, raw):
        need(not self._closed, 'Session already closed')
        need(type(raw) is bytes, 'Byte-framed participant input')
        need(0 < len(raw) <= REQUEST_CAP, 'Bounded typed request before hashing')
        need(self._attempts < self._action_limit, 'Action allowance exhausted')
        self._attempts += 1
        request = None
        try:
            request = strict(raw)
            value = self._dispatch(request)
            response = encoded({'ok': True, 'result': value})
        except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError, KeyError):
            response = encoded({'ok': False, 'error': 'invalid_typed_request'})
            value = None
        need(self._bytes + len(response) <= self._output_limit, 'Output allowance exhausted')
        self._bytes += len(response)
        event = {'sequence': self._attempts, 'request': pin(raw), 'response': pin(response), 'previous': self._chain}
        self._chain = hashlib.sha256(encoded(event)).hexdigest()
        self._events.append(event | {'sha256': self._chain})
        if value is not None:
            if request['action'] == 'answer':
                self._answers[request['index']] = list(request['velocity'])
            elif request['action'] == 'view':
                self._views.append({key: request[key] for key in ('split', 'index', 'units', 'bins')})
            elif request['action'] == 'finish':
                self._closed = True
        return response

    def receipt(self):
        """Operator-only attestation data; source validity and delivery are external."""
        return {'schema': 'neural022_typed_count_viewer_receipt_v1', 'condition': CONDITION,
                'export': self._export, 'observation': self._observation,
                'complete': self._closed and len(self._answers) == 92,
                'answers': len(self._answers), 'attempted_actions': self._attempts,
                'output_bytes': self._bytes, 'event_chain': self._chain,
                'events': list(self._events), 'views': list(self._views),
                'external_provider_verified': False, 'external_isolation_verified': False,
                'image_rendering_verified': False, 'no_tools_behavior_verified': False,
                'scientific_qualification': False, 'private_targets_loaded': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--export-sha256', required=True)
    args = parser.parse_args(argv)
    raw, manifest = load_export(args.export, args.export_sha256)
    session = Session(raw, manifest, args.export_sha256)
    while not session._closed:
        request = sys.stdin.buffer.readline(REQUEST_CAP + 1)
        if not request:
            raise ValueError('Participant stream ended before complete92 finish')
        need(len(request) <= REQUEST_CAP and request.endswith(b'\n'), 'One bounded JSON line')
        reply = session.apply(request)
        sys.stdout.buffer.write(reply); sys.stdout.buffer.flush()
    # The external operator must retain this bounded stderr receipt and observe
    # exit0/closure; a participant-facing finish response cannot replace that proof.
    receipt = encoded(session.receipt())
    need(len(receipt) <= RECEIPT_CAP, 'Bounded complete operator receipt')
    sys.stderr.buffer.write(receipt); sys.stderr.buffer.flush()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
