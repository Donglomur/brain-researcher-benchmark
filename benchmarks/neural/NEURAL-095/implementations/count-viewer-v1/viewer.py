"""Operator-custodied full-panel count viewer, replay, collection and paired scoring.

The typed interface is executable; external model isolation and study budgets
are not established by this local broker. No candidate code executes here.
"""
import argparse
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import stat
import sys
import types
import zlib

import numpy as np

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[4]
MODE = 'restricted_count_viewer/v1'
VIEWS = ('cue_only', 'neural')
FILES = ('train.npz', 'query.npz', 'schema.json', 'units.json', 'contract.json')
COMMON = {'case_id', 'condition', 'context', 'nominal_ts_ms', 'clock_seconds'}
MAX_HISTORY = 64 * 1024**2
MAX_ACTIONS = 20000  # Software safety bound, not a qualified model/study budget.
MAX_LINE = 16384


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def encoded(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(body):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'Duplicate JSON key')
            out[key] = value
        return out
    def invalid(value):
        raise ValueError('Nonfinite JSON constant')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def identity(st):
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_nlink


def capture(path, cap):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'Unlinked file and ancestors required')
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap, 'Bounded ordinary file required')
    with path.open('rb') as stream:
        need(identity(os.fstat(stream.fileno())) == identity(before), 'File changed before capture')
        body = stream.read(cap + 1)
        need(identity(os.fstat(stream.fileno())) == identity(before), 'File changed during capture')
    need(len(body) == before.st_size and identity(path.stat()) == identity(before) and
         all(not p.is_symlink() for p in (path, *path.parents)), 'Stable complete file capture required')
    return body


def pinned(path, expected):
    need(set(expected) == {'bytes', 'sha256'} and type(expected['bytes']) is int and
         0 < expected['bytes'] <= MAX_HISTORY, 'Bounded exact file descriptor')
    body = capture(path, expected['bytes'])
    need(pin(body) == expected, 'File identity mismatch')
    return body


def save(path, body):
    path = Path(path)
    need(type(body) is bytes and 0 < len(body) <= MAX_HISTORY, 'Bounded output')
    with path.open('xb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o400)


class Sources:
    def __init__(self):
        manifest_body = capture(HERE / 'SOURCE.json', 64000)
        self.manifest = decode(manifest_body)
        need(self.manifest['schema'] == 'neural095-count-viewer-source/v1', 'Source manifest')
        self.bodies = {role: pinned(ROOT / row['path'], row['pin']) for role, row in self.manifest['files'].items()}
        self.identity = {'manifest': pin(manifest_body), 'source_files': {key: pin(body) for key, body in self.bodies.items()}}
        self.expected = decode(self.bodies['expected'])
        self.artifacts = decode(self.bodies['artifacts'])
        self.modules = {}
        for role in ('project', 'validator', 'metrics', 'paired', 'raster', 'render'):
            module = types.ModuleType('_neural095_viewer_' + role)
            module.__file__ = str(ROOT / self.manifest['files'][role]['path'])
            exec(compile(self.bodies[role], module.__file__, 'exec'), module.__dict__)
            self.modules[role] = module
        self.runtime = {'python': platform.python_version(), 'numpy': np.__version__,
                        'zlib_build': zlib.ZLIB_VERSION, 'zlib_runtime': zlib.ZLIB_RUNTIME_VERSION}


def public_arrays(body, fields, n, project):
    members, inventory = project.members(body, fields, n)
    # Original header/CRC/expanded-size admission precedes any numeric load.
    out = {key: np.load(io.BytesIO(value), allow_pickle=False) for key, value in members.items()}
    need(len(set(out['case_id'].tolist())) == n and all(type(x) is str and len(x) == 11 and x.startswith('dmfc-')
         and all(c in '0123456789' for c in x[5:]) for x in out['case_id'].tolist()), 'Canonical complete IDs')
    c, context = out['condition'], out['context']
    need(set(c.tolist()) == set(range(40)) and np.array_equal(context, c // 5), 'All 40 conditions and eight contexts')
    nominal = np.array([800, 900, 1000, 1100, 1200] * 4 + [480, 560, 640, 720, 800] * 4)
    need(np.array_equal(out['nominal_ts_ms'], nominal[c]), 'Original condition-specific nominal levels')
    for key in ('nominal_ts_ms', 'clock_seconds'):
        need(np.isfinite(out[key]).all(), 'Finite public cues')
    need(np.all(out['clock_seconds'] >= 0) and np.all(np.diff(out['clock_seconds']) >= 0), 'Original chronological elapsed clocks')
    if 'tp_ms' in fields:
        need(np.isfinite(out['tp_ms']).all() and np.all(out['tp_ms'] > 0) and set(out['fold'].tolist()) == set(range(5)),
             'Complete training targets and original five folds')
    for value in out.values():
        value.flags.writeable = False
    return out, {key: row['sha256'] for key, row in inventory.items() if key != 'counts'}


class Packet:
    def __init__(self, view, files, sources):
        need(view in VIEWS and type(files) is dict and set(files) == set(FILES), 'One exact public view file mapping')
        self.view, self.sources = view, sources
        bodies = {name: pinned(files[name], sources.expected['views'][view + '/' + name]) for name in FILES}
        self.pins = {name: pin(body) for name, body in bodies.items()}
        self.schema, self.contract, units = (decode(bodies[key]) for key in ('schema.json', 'contract.json', 'units.json'))
        need(self.schema['train_n'] == 748 and self.schema['query_n'] == 258 and self.schema['paired_observation_view'] == view
             and self.schema['bin_edges_seconds_relative_to_Set'] == [-.2, -.15, -.1, -.05, 0.]
             and self.schema['bin_convention'] == '[left,right)' and self.schema['counts_available'] is (view == 'neural'), 'Exact original view schema')
        need(set(units) == {'unit_id', 'source'} and len(units['unit_id']) == 40 and len(set(units['unit_id'])) == 40
             and all(type(x) is int and 0 <= x <= 9999999999 for x in units['unit_id']), 'Original full unit metadata')
        self.units = tuple(units['unit_id'])
        self.arrays, self.common = {}, {}
        for split, n in (('train', 748), ('query', 258)):
            fields = COMMON | ({'tp_ms', 'fold'} if split == 'train' else set()) | ({'counts'} if view == 'neural' else set())
            need(set(self.schema['public_keys'][split]) == fields, 'Original public field allowlist')
            self.arrays[split], self.common[split] = public_arrays(bodies[split + '.npz'], fields, n, sources.modules['project'])
        need(not set(self.arrays['train']['case_id'].tolist()) & set(self.arrays['query']['case_id'].tolist()), 'Disjoint original train/query IDs')
        self.ids = self.arrays['query']['case_id'].tolist()

    def metadata(self, split, index):
        need(split in ('train', 'query') and type(index) is int and 0 <= index < (748 if split == 'train' else 258), 'Invalid observation request')
        values = self.arrays[split]
        keys = COMMON | ({'tp_ms', 'fold'} if split == 'train' else set())
        return {'view': self.view, 'split': split, 'index': index,
                **{key: values[key][index].item() for key in sorted(keys)}}

    def show(self, split, index):
        metadata = self.metadata(split, index)
        counts = self.arrays[split]['counts'][index].tolist() if self.view == 'neural' else None
        image, pixels = self.sources.modules['render'].render(metadata, counts, self.units, self.sources.modules['raster'])
        observation = {'metadata': metadata, 'unit_ids': list(self.units), 'representation': 'four_by_forty_uint32_count_table' if counts is not None else 'cues_only',
                       'bin_edges_ms_relative_to_Set': [-200, -150, -100, -50, 0], 'bin_convention': '[left,right)',
                       'image': pin(image), 'pixels': pin(pixels), 'width': 1400, 'height': 820, 'mode': 'RGB'}
        return observation, image

    def header(self):
        return {'type': 'header', 'condition': MODE, 'view': self.view, 'source': self.sources.identity,
                'runtime': self.sources.runtime, 'inputs': self.pins, 'common_members': self.common,
                'query_ids': self.ids, 'train_n': 748, 'query_n': 258,
                'unit_ids': list(self.units), 'training_fold_visible': True,
                'question': 'Predict released behavioral tp in milliseconds at observed Set for every query. Use all offered training context; finite negative predictions remain admissible.',
                'instructions': 'Use only show_train, show_query and answer. Do not fit preprocessing on query rows, run code or obtain query feedback. Browse any case; answer in the original query order. Begin each view with a fresh participant context and do not transfer opposite-view observations or answers.',
                'query_feedback': False, 'full_query_browsing': True, 'query_preprocessing_fit_allowed': False,
                'participant_isolation_verified': False, 'provider_study_budget_qualified': False}


class Session:
    def __init__(self, packet):
        self.packet, self.answers, self.seen = packet, [], set()
        self.actions = 0
        self.observation_count = 0
        self.rendered_png_bytes = 0
        self.rendered_rgb_bytes = 0

    def step(self, action):
        need(type(action) is dict and self.actions < MAX_ACTIONS, 'Invalid or exhausted action')
        op = action.get('op')
        if op in ('show_train', 'show_query'):
            need(set(action) == {'op', 'index'}, 'Invalid observation action')
            split = op[5:]
            observation, image = self.packet.show(split, action['index'])
            self.observation_count += 1
            self.rendered_png_bytes += len(image)
            self.rendered_rgb_bytes += observation['pixels']['bytes']
            if split == 'query':
                self.seen.add(action['index'])
            event = {'action': action, 'observation': observation}
            response = {'observation': observation, 'image_png_base64': base64.b64encode(image).decode('ascii')}
        elif op == 'answer':
            need(set(action) == {'op', 'case_id', 'prediction_ms'} and len(self.answers) < 258, 'Invalid answer action')
            index, value = len(self.answers), action['prediction_ms']
            need(action['case_id'] == self.packet.ids[index] and index in self.seen, 'Expected viewed next query in original order')
            need(type(value) in (int, float), 'Finite scalar prediction required')
            try:
                value = float(value)
            except (ValueError, OverflowError):
                raise ValueError('Finite scalar prediction required') from None
            need(math.isfinite(value), 'Finite scalar prediction required')
            normalized = {'op': 'answer', 'case_id': action['case_id'], 'prediction_ms': value}
            self.answers.append(value)
            event = {'action': normalized, 'answer_index': index}
            response = {'accepted': action['case_id'], 'answered': len(self.answers)}
        else:
            raise ValueError('Unsupported action')
        self.actions += 1
        return event, response

    def finish(self):
        need(len(self.answers) == 258, 'All 258 immutable answers required')
        return {'type': 'complete', 'condition': MODE, 'view': self.packet.view, 'actions': self.actions,
                'query_ids': self.packet.ids, 'prediction_identity': pin(encoded(self.answers)),
                'training_available': 748, 'queries_answered': 258, 'query_feedback': False,
                'observation_count': self.observation_count, 'rendered_png_bytes': self.rendered_png_bytes,
                'rendered_rgb_bytes': self.rendered_rgb_bytes,
                'render_accounting_scope': 'Per replayed session image bytes before base64. Includes repeated views; excludes wire framing, model costs and collection replay CPU.'}


def replay(packet, history_body):
    need(type(history_body) is bytes and 0 < len(history_body) <= MAX_HISTORY and history_body.endswith(b'\n'), 'Bounded complete history')
    lines = history_body.splitlines()
    need(2 <= len(lines) <= MAX_ACTIONS + 2 and all(0 < len(x) <= MAX_LINE for x in lines), 'Bounded complete history lines')
    need(decode(lines[0]) == packet.header(), 'Exact original view, runtime, sources and ordered roster required')
    session = Session(packet)
    for line in lines[1:-1]:
        recorded = decode(line)
        need(type(recorded) is dict and 'action' in recorded, 'History event required')
        event, _ = session.step(recorded['action'])
        need(event == recorded, 'Replayed observation or immutable answer differs')
    need(decode(lines[-1]) == session.finish(), 'Exact complete receipt required')
    return np.array(session.answers, dtype=np.float64)


def submission(ids, predictions):
    import zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, value in (('case_id', np.array(ids, dtype='<U11')), ('prediction_ms', np.array(predictions, dtype='<f8'))):
            payload = io.BytesIO(); np.save(payload, value, allow_pickle=False)
            info = zipfile.ZipInfo(name + '.npy', date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3; info.external_attr = (stat.S_IFREG | 0o400) << 16
            archive.writestr(info, payload.getvalue())
    return buffer.getvalue()


def pair_packets(packets):
    need(set(packets) == set(VIEWS) and all(packets[v].view == v for v in VIEWS), 'Both distinct views required')
    a, b = (packets[v] for v in VIEWS)
    need(a.ids == b.ids and a.common == b.common and a.units == b.units, 'Original identical common members and full ordered cases required')


def collect(packets, histories, out):
    pair_packets(packets)
    need(set(histories) == set(VIEWS), 'Both complete histories required')
    bodies = {v: capture(histories[v], MAX_HISTORY) for v in VIEWS}
    vectors = {v: replay(packets[v], bodies[v]) for v in VIEWS}
    out = Path(out).absolute(); out.mkdir(mode=0o700, parents=False, exist_ok=False)
    files = {}
    for view in VIEWS:
        path = out / (view + '.npz')
        body = submission(packets[view].ids, vectors[view]); save(path, body)
        checked = packets[view].sources.modules['validator'].validate(path, packets[view].ids)
        need(np.array_equal(checked, vectors[view]), 'Original validator parity')
        files[view] = pin(body)
    receipt = {'condition': MODE, 'status': 'both_complete_viewer_histories_replayed', 'query_ids': packets['cue_only'].ids,
               'histories': {v: pin(bodies[v]) for v in VIEWS}, 'submissions': files,
               'headers': {v: packets[v].header() for v in VIEWS}, 'research_qualified': False,
               'participant_transport_verified': False, 'external_no_tools_enforced': False}
    save(out / 'COLLECTION.json', encoded(receipt))
    return receipt


def validate_collection(packets, histories, collection):
    pair_packets(packets)
    need(set(histories) == set(VIEWS), 'Both history operands')
    collection = Path(collection)
    receipt = decode(capture(collection / 'COLLECTION.json', MAX_HISTORY))
    bodies = {v: capture(histories[v], MAX_HISTORY) for v in VIEWS}
    vectors = {v: replay(packets[v], bodies[v]) for v in VIEWS}
    expected = {'condition': MODE, 'status': 'both_complete_viewer_histories_replayed', 'query_ids': packets['cue_only'].ids,
                'histories': {v: pin(bodies[v]) for v in VIEWS}, 'headers': {v: packets[v].header() for v in VIEWS},
                'research_qualified': False, 'participant_transport_verified': False, 'external_no_tools_enforced': False}
    actual_pins = {}
    for view in VIEWS:
        path = collection / (view + '.npz')
        body = capture(path, 1024**2)
        need(body == submission(packets[view].ids, vectors[view]), 'Exact canonical complete replayed submission required')
        checked = packets[view].sources.modules['validator'].validate(path, packets[view].ids)
        need(np.array_equal(checked, vectors[view]) and capture(path, 1024**2) == body, 'Stable original public validation')
        actual_pins[view] = pin(body)
    need(receipt == {**expected, 'submissions': actual_pins}, 'Exact paired collection receipt')
    return vectors, receipt


def evaluate(packets, histories, collection, reference_loader, private_loader):
    # Both public replay and complete submissions before even calling private/reference loaders.
    vectors, receipt = validate_collection(packets, histories, collection)
    references = reference_loader()
    value = private_loader()
    ids = packets['cue_only'].ids
    need(type(value) is dict and set(value) == {'case_id', 'tp_ms', 'condition', 'context'} and
         np.asarray(value['case_id']).tolist() == ids, 'Private/public exact complete identity order')
    for key in ('condition', 'context'):
        need(np.array_equal(value[key], packets['cue_only'].arrays['query'][key]), 'Original query cue/private join')
    sources = packets['cue_only'].sources
    arms = {v: sources.modules['metrics'].score_candidate(vectors[v], lambda: value, references) for v in VIEWS}
    paired = sources.modules['paired']
    difference = paired.pair_difference(vectors['cue_only'], vectors['neural'], value['tp_ms'], value['condition'], value['context'])
    checks = paired.verify_paired_arithmetic(difference, arms['cue_only']['candidate'], arms['neural']['candidate'])
    return {'candidate_id': 'NEURAL-095', 'condition': MODE, 'status': 'viewer_pair_artifacts_scored', 'arms': arms,
            'paired': difference, 'paired_arithmetic_checks': len(checks), 'collection': pin(encoded(receipt)),
            'cases_per_view': 258, 'private_loader_calls': 1, 'new_reference_fits': 0, 'candidate_code_executed': False,
            'research_qualified': False, 'matched_method_proven': False, 'native_understanding_proven': False,
            'provider_execution_or_budget_qualified': False, 'cross_condition_causal_effect_claimed': False}


def loaders(sources, files, ids):
    # Building closures does not stat/hash/open protected paths. Invoked only after public validation.
    need(type(files) is dict and set(files) == set(sources.artifacts['files']), 'Exact five evaluator operands')
    expected = sources.artifacts
    def read(name):
        return pinned(files[name], expected['files'][name])
    def references():
        identity_doc = decode(read('public_identity.json'))
        need(identity_doc == {'schema_version': 1, 'case_id': ids}, 'Pinned original public roster')
        grade, commit, audit = (decode(read(name)) for name in ('reference_grade.json', 'reference_commit.json', 'reference_audit.json'))
        need(commit['status'] == 'producer_removed_outputs_committed' and commit['all_owned_producers_absent'] is True and
             commit['predictions'] == expected['reference_prediction_identity'] and commit['public_identity'] == expected['files']['public_identity.json'] and
             commit['private_targets'] == expected['files']['query_targets.npz'], 'Original reference custody')
        need(grade['status'] == 'continuous_fixed_reference_panel_scored' and grade['candidate_id'] == 'NEURAL-095' and
             grade['public_validation_before_private_decode'] is True and grade['private_loader_invocations'] == 1 and
             grade['predictions'] == commit['predictions'] and set(grade['scores']) == set(sources.modules['metrics'].METHODS), 'Original five fixed references')
        need(audit['status'] == 'passed' and audit['independent_scalar_checks'] == 280 and audit['score_sha256'] == expected['files']['reference_grade.json']['sha256'], 'Original audited reference grade')
        return grade
    def private():
        body = read('query_targets.npz')
        with np.load(io.BytesIO(body), allow_pickle=False) as archive:
            return {key: archive[key] for key in archive.files}
    return references, private


def serve(packet, history, source, sink):
    session = Session(packet)
    history = Path(history)
    with history.open('xb') as journal:
        history.chmod(0o600)
        written = 0
        def persist(row):
            nonlocal written
            body = encoded(row); need(len(body) <= MAX_LINE and written + len(body) <= MAX_HISTORY, 'History bound')
            journal.write(body); journal.flush(); os.fsync(journal.fileno()); written += len(body)
        persist(packet.header())
        sink.write(encoded(packet.header())); sink.flush()
        while True:
            line = source.readline(MAX_LINE + 1)
            need(line and len(line) <= MAX_LINE and line.endswith(b'\n'), 'Bounded complete action line required')
            action = decode(line)
            if action == {'op': 'finish'}:
                receipt = session.finish(); persist(receipt)
                sink.write(encoded(receipt)); sink.flush(); return
            event, response = session.step(action)
            # A failed journal write ends the process before acknowledgement or any later observation.
            persist(event)
            sink.write(encoded(response)); sink.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('serve', 'collect', 'grade'))
    parser.add_argument('--inputs', type=Path, required=True, help='Operator JSON: cue_only/neural -> five original public file paths')
    parser.add_argument('--view', choices=VIEWS)
    parser.add_argument('--history', type=Path)
    parser.add_argument('--cue-history', type=Path)
    parser.add_argument('--neural-history', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--collection', type=Path)
    parser.add_argument('--evaluator-inputs', type=Path)
    args = parser.parse_args()
    sources = Sources(); inputs = decode(capture(args.inputs, 64000))
    if args.command == 'serve':
        need(args.view is not None and args.history is not None, 'View and fresh history required')
        need(type(inputs) is dict and set(inputs) == {args.view}, 'Serve mapping must contain only the selected view')
        serve(Packet(args.view, inputs[args.view], sources), args.history, sys.stdin.buffer, sys.stdout.buffer)
    else:
        need(type(inputs) is dict and set(inputs) == set(VIEWS) and args.cue_history and args.neural_history, 'Paired public inputs and histories required')
        packets = {v: Packet(v, inputs[v], sources) for v in VIEWS}
        histories = {'cue_only': args.cue_history, 'neural': args.neural_history}
        if args.command == 'collect':
            need(args.out is not None, 'Fresh collection output required')
            print(json.dumps(collect(packets, histories, args.out), allow_nan=False))
        else:
            need(args.collection and args.evaluator_inputs and args.out, 'Collection, evaluator locator and fresh grade output required')
            # This locator contains paths only. Targets themselves are untouched until evaluate admits both views.
            files = decode(capture(args.evaluator_inputs, 64000))
            reference_loader, private_loader = loaders(sources, files, packets['cue_only'].ids)
            save(args.out, encoded(evaluate(packets, histories, args.collection, reference_loader, private_loader)))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Deliberately no source values, paths, targets or parser payload in participant errors.
        print('NEURAL-095 operation refused; no later observation or assessment released.', file=sys.stderr)
        raise SystemExit(2)
