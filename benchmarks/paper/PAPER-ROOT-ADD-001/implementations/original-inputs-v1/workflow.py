"""Connect complete original inputs/predictions to the existing224-file reducer."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from inputs import ArchiveInputs, bindings, need, pin, reducer
from prediction import compute_session, smooth_targets


def array_pin(value):
    value = np.ascontiguousarray(value)
    return {'shape': list(value.shape), 'dtype': value.dtype.str,
            'sha256_c_order': hashlib.sha256(value.tobytes()).hexdigest()}


def validate_weights(weights, session_order):
    need(weights.get('schema') == 'language-original-population-weights/v1'
         and [r['session'] for r in weights.get('rows', [])] == list(session_order),
         'Complete ordered original weight roster required')
    counts = []
    for row in weights['rows']:
        count = row['count']
        need(type(count) is int and 0 < count <= 4096 and row['shape'][0] == count
             and row['member'] == f"data_processed/{row['session']}/self_FR_aligned2word.npy"
             and row['receipt']['full_member_crc_verified'] is True
             and row['receipt']['array_values_decoded'] is False
             and len(row['receipt']['sha256']) == 64,
             'Authentic weight-header receipt required; no fr column-count substitute')
        counts.append(count)
    return np.asarray(counts, dtype=np.float64)


def summarize_with_weights(panel, weights):
    source_panel, figure3 = reducer()
    source_panel.validate_panel(panel)
    counts = validate_weights(weights, source_panel.SESSION_UNITS)
    # Literal notebook weighted sum, distinct from the equal-session Figure3b.
    weighted = (np.stack([panel[s]['population'] for s in source_panel.SESSION_UNITS])
                * (counts / counts.sum())[:, None, None]).sum(axis=0)
    maximum = weighted.max()
    normalized = (weighted / maximum if np.isfinite(maximum) and maximum != 0
                  else np.full_like(weighted, np.nan))
    report = figure3.summarize(panel)
    report['figure3e'].update({'weighted_population_status': 'computed_from_original_self_FR_headers',
        'weighted_population_mean': figure3.finite_json(weighted),
        'weighted_population_normalized': figure3.finite_json(normalized),
        'source_session_weights': (counts / counts.sum()).tolist(),
        'source_session_neuron_counts': counts.astype(int).tolist(),
        'weight_provenance': weights})
    report['cohort_identity_status'] = {
        'self_FR_weight_count': int(counts.sum()),
        'fr_matrix_columns': sum(source_panel.SESSION_UNITS.values()),
        'source_selectivity_rows': 579,
        'cross_representation_unit_join_authenticated': False,
        'meaning': 'Separate native populations; matching totals do not establish neuron identity'}
    report['scientific_qualification'] = False
    return report


class PredictionDigestSink:
    """Bound every observation product without retaining raw predictions.

    This is an execution trace, not independent custody or a recoverable prediction
    artifact. Operators may instead supply a budgeted sink storing all products.
    """
    def __init__(self):
        self.count, self.digest = 0, hashlib.sha256()

    def __call__(self, record):
        row = {k: record[k] for k in ('session', 'field', 'family', 'layer', 'lag_index', 'lag_bins', 'folds')}
        row['arrays'] = {key: array_pin(record[key]) for key in ('qid', 'time_indices', 'predictions', 'targets')}
        self.digest.update(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False).encode() + b'\n')
        self.count += 1

    def receipt(self):
        return {'jobs': self.count, 'ordered_observation_trace_sha256': self.digest.hexdigest(),
                'raw_predictions_retained': False, 'independent_execution_authenticated': False}


class ExclusiveOutput:
    def __init__(self, root, *, byte_limit):
        need(type(byte_limit) is int and byte_limit > 0, 'Explicit output byte allocation required')
        self.root = Path(root).absolute()
        need(not any(p.is_symlink() for p in self.root.parents), 'No output symlink ancestors')
        self.root.mkdir(mode=0o700)
        self.limit, self.written, self.files = byte_limit, 0, {}

    def write(self, relative, raw):
        relative = Path(relative)
        need(not relative.is_absolute() and '..' not in relative.parts
             and str(relative) not in self.files, 'Fresh relative output path required')
        need(self.written + len(raw) <= self.limit, 'Output allocation exceeded')
        path = self.root / relative
        need(not any(p.is_symlink() for p in (path, *path.parents)), 'No output symlink path')
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        need(not any(p.is_symlink() for p in (path, *path.parents)), 'No output symlink path')
        with path.open('xb') as stream:
            path.chmod(0o600)
            self.written += len(raw)  # Charge the attempted write, including failure.
            stream.write(raw)
        receipt = {'path': relative.as_posix(), **pin(raw)}
        self.files[relative.as_posix()] = receipt
        return receipt

    def json(self, relative, value):
        return self.write(relative, (json.dumps(value, indent=2, allow_nan=False) + '\n').encode())


def prepare_inventory(reader):
    """Full source input preparation/census; no fitting or prediction scores."""
    weights = reader.population_weights()
    sessions = []
    for session in reader.geometry:
        data = reader.load_session(session)
        population, units = smooth_targets(data['fr'])
        sessions.append({'session': session, 'geometry': data['geometry'],
                         'csv_row_order_preserved': True,
                         'original_qid': array_pin(data['qid']), 'original_timing': array_pin(data['timing']),
                         'prepared_population_response': array_pin(population),
                         'prepared_unit_responses': array_pin(units),
                         'source_unit_ids': 'session identifier plus zero-based original fr_matrix column',
                         'input_receipts': data['input_receipts']})
    return {'schema': 'language-original-input-preparation/v1',
            'sessions': sessions, 'population_weights': weights,
            'archive_receipts': reader.archive_receipts,
            'logical_source_read_charge_bytes': reader.charged,
            'prepared_arrays_persisted': False, 'models_fitted': 0,
            'scientific_qualification': False,
            'population_unit_identity_join_authenticated': False}


def produce_panel(reader, predictor, output, *, max_requests):
    """Produce all224 original result files through a trusted operator callback.

    Caller must separately admit model runtime and request counts. This function
    is never invoked by preparation CLI or generated archive controls.
    """
    source_panel, _ = reducer()
    need(list(reader.geometry) == list(source_panel.SESSION_UNITS), 'Complete original source session roster')
    need(type(max_requests) is int and max_requests > 0, 'Explicit full-run request allocation')
    weights, panel, provenance, requests = reader.population_weights(), {}, [], 0
    for session in source_panel.SESSION_UNITS:
        data, sink = reader.load_session(session), PredictionDigestSink()
        fields, receipt = compute_session(data, predictor, max_requests=max_requests - requests, sink=sink)
        # Validate the complete session before publishing any of its result files.
        expected = source_panel.shapes(session)
        need(set(fields) == set(expected), 'Every source result field required')
        for field, shape in expected.items():
            value = fields[field]
            need(value.shape == shape and value.dtype == np.float64
                 and not np.isinf(value).any() and np.all(np.abs(value[np.isfinite(value)]) <= 1),
                 'Original result geometry/correlation range')
        rows = []
        for field, filename in source_panel.SOURCE_FILES.items():
            buffer = io.BytesIO()
            np.save(buffer, fields[field], allow_pickle=False)
            rows.append(output.write(f'result_llm/{session}/{filename}', buffer.getvalue()))
        panel[session] = fields
        requests += receipt['sentence_prediction_requests']
        provenance.append({'session': session, 'computation': receipt,
                           'prediction_products': sink.receipt(), 'output_files': rows})
    source_panel.validate_panel(panel)
    need(sum(len(r['output_files']) for r in provenance) == 224, 'Complete224-file panel required')
    report = summarize_with_weights(panel, weights)
    report['prediction_provenance'] = provenance
    report['archive_receipts'] = reader.archive_receipts
    report['prediction_requests'] = requests
    report['logical_source_read_charge_bytes'] = reader.charged
    report['candidate_identity_authenticated'] = False
    output.json('RESULT.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description='Prepare all original language inputs; no model execution')
    parser.add_argument('--data-archive', required=True)
    parser.add_argument('--dnn-archive', required=True)
    parser.add_argument('--transcription-archive', required=True)
    parser.add_argument('--logical-read-limit', type=int, required=True)
    parser.add_argument('--working-limit', type=int, required=True)
    parser.add_argument('--output-limit', type=int, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    paths = {'data_processed.zip': args.data_archive, 'DNN.zip': args.dnn_archive,
             'transcription.zip': args.transcription_archive}
    with ArchiveInputs(paths, read_limit=args.logical_read_limit, working_limit=args.working_limit) as reader:
        report = prepare_inventory(reader)
    output = ExclusiveOutput(args.output, byte_limit=args.output_limit)
    output.json('PREPARATION.json', report)


if __name__ == '__main__':
    main()
