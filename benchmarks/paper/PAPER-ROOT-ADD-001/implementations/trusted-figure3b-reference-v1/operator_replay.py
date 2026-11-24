"""Fixed trusted original Figure 3b reference; never a participant executor.

The operator can read original targets. The frozen source predictor receives
only each held-qid's training labels. No programme selection, search, retries,
parallel fits or NativeProvider admission is implemented here.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import time


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def put(path, body, cap):
    need(type(body) is bytes and len(body) <= cap, 'Bounded fixed output')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return pin(body)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def source_modules(source):
    directory = source/'original-figure3b-store-v1'
    producer = load('producer', directory/'producer.py')
    reader = load('_fixed_operator_store_reader', directory/'reader.py')
    endpoint = load('_fixed_operator_endpoint', source/'original-figure3b-improvement-v1/improvement.py')
    reference = load('_fixed_operator_provided_reference', source/'original-figure3b-execution-v1/reference.py')
    return producer, reader, endpoint, reference


def bind_job(session, item, expected_context):
    need(item['context'] == expected_context, 'Complete canonical original context order')
    need(item['outputs'] == 1 and 'targets' in item, 'Original population target is operator-side')
    x = session._candidate_array(item['view_job'].feature_id)
    need(x.shape == (len(item['qid']), 30) and item['targets'].shape == (len(item['qid']), 1),
         'Exact original selected feature and target shapes')
    return {**item['context'], 'x': x, 'y': item['targets'],
            'qid': item['qid'], 'time_indices': item['time_indices']}


def complete_counts(contexts, expected, fits):
    need(contexts == list(expected) and len(contexts) == 42 and fits == 5685,
         'All 42 original cells and 5685 fresh fits required; no partial score')


def run(protocol, source, store, reference_path, output):
    import numpy as np
    import scipy
    import sklearn
    versions = {'numpy': np.__version__, 'scipy': scipy.__version__, 'sklearn': sklearn.__version__}
    need(versions == {'numpy': '1.24.3', 'scipy': '1.10.1', 'sklearn': '1.2.2'},
         'Frozen historical numerical stack')
    need(sys.version_info[:3] == (3, 11, 3), 'Retained Python 3.11.3 image')
    started = time.monotonic()
    producer, reader_module, endpoint, reference_module = source_modules(source)
    # This existing dedicated trusted adapter checks the same numerical stack
    # and creates a new Ridge(alpha=.01) inside every callback.
    source_predictor = producer.O.source_ridge_predictor()
    from threadpoolctl import threadpool_info
    pools = threadpool_info()
    need(pools and all(row['num_threads'] == 1 for row in pools), 'One numerical thread in every loaded pool')
    actual_calls = 0
    operand_bytes = 0
    def predictor(train_x, train_y, query_x, context):
        nonlocal actual_calls, operand_bytes
        result = source_predictor(train_x, train_y, query_x, context)
        actual_calls += 1
        operand_bytes += train_x.nbytes + train_y.nbytes + query_x.nbytes
        return result
    expected = endpoint.contexts()
    reader = reader_module.StoreReader(store, expected_store_sha256=protocol['store_sha256'],
        read_limit=protocol['store_read_limit'], working_limit=protocol['working_limit'])
    contexts, scores, records = [], [], []
    fits = 0
    total_output = 0
    try:
        need(reader.scope == 'original_figure3b_improvement', 'Authentic complete selected store')
        for session in reader.iter_sessions():
            for item in session.iter_jobs(include_targets=True):
                index = len(contexts)
                need(index < 42, 'No extra context')
                job = bind_job(session, item, expected[index])
                captured = []
                def sink(value):
                    need(not captured, 'Exactly one completed observation per source job')
                    captured.append(value)
                corr, used = producer.O.predict_job(job, predictor,
                    remaining_requests=5685-fits, sink=sink)
                need(len(captured) == 1 and used == len(item['view_job'].response_shards),
                     'Complete held-sentence fit roster')
                observed = captured[0]
                raw = np.asarray(observed['predictions'], dtype='<f8').tobytes(order='C')
                need(len(raw) == 8*len(item['qid']), 'Complete population prediction rows')
                receipt = {
                    'context': item['context'], 'fits': used, 'rows': len(item['qid']),
                    'source_target_sha256': item['target_sha256'],
                    'source_support_class_sha256': item['support_class_sha256'],
                    'qid_sha256': producer.p.array_sha(item['qid']),
                    'time_indices_sha256': producer.p.array_sha(item['time_indices']),
                    'prediction': pin(raw), 'prediction_shape': [len(item['qid']), 1],
                    'prediction_dtype': '<f8', 'folds': observed['folds'],
                    'pearson_r': None if np.isnan(corr[0]) else float(corr[0])}
                receipt_body = encoded(receipt)
                next_output = total_output + len(raw) + len(receipt_body)
                need(next_output <= protocol['output_limit'], 'Complete operation output limit')
                put(output/f'prediction-{index:02d}.f64le', raw, protocol['output_limit'])
                put(output/f'cell-{index:02d}.json', receipt_body, protocol['output_limit'])
                total_output = next_output
                contexts.append(item['context'])
                scores.append({'context': item['context'], 'pearson_r': receipt['pearson_r']})
                records.append({'cell': index, 'receipt': pin(receipt_body), 'prediction': pin(raw)})
                fits += used
                # Completion-only progress; no scores or predictions in logs.
                print(json.dumps({'completed_cells': len(contexts), 'completed_fits': fits}), flush=True)
        complete_counts(contexts, expected, fits)
        need(actual_calls == fits == 5685, 'Every completed request used the fixed fresh-estimator source callback')
        reader_costs = {'bytes_read': reader.bytes_read, 'charged_read_bytes': reader.read_charged,
                        'peak_declared_working_admission_bytes': reader.peak_working_admission}
    finally:
        reader.close()
    # Only now read the fixed provided result. It never enters predictor inputs.
    provided = reference_module.load(reference_path)
    raw_run = pin(encoded(records))['sha256']
    packet = {'schema': 'language-original-figure3b-scores/v1', 'role': 'candidate',
        'selection_sha256': hashlib.sha256(endpoint.encoded(endpoint.selection())).hexdigest(),
        'source_support_sha256': reference_module.CENSUS_SHA, 'prediction_run_sha256': raw_run,
        'scores': scores, 'execution_qualified': False}
    comparison = endpoint.compare(packet, provided)
    result = {'schema': 'language-trusted-operator-reference/v1', 'status': 'complete_fixed_author_replay',
        'role': 'trusted_operator_author_reference', 'sessions': 14, 'people': 8,
        'cells': 42, 'fresh_estimator_fits': fits, 'versions': versions,
        'actual_source_predictor_calls': actual_calls,
        'repeated_in_memory_predictor_operand_bytes': operand_bytes,
        'python': sys.version.split()[0], 'numerical_threadpools': pools, 'prediction_records': records,
        'scores': scores, 'source_reader_costs': reader_costs,
        'comparison_with_provided_author': comparison,
        'comparison_interface_role_is_candidate_only_for_existing_reducer': True,
        'AI_candidate_or_improvement_result': False, 'participant_provider_qualified': False,
        'participant_isolation_exercised': False, 'whole_224_array_reproduction': False,
        'SOTA_claim': False, 'tuning_or_selection': False, 'automatic_retry': False,
        'target_custody': 'Trusted operator reads targets for fixed training/scoring; frozen predictor receives train labels only.',
        'source_reference_read_after_all_fits': True,
        'elapsed_seconds': time.monotonic()-started,
        'worker_peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        'rss_scope': 'Linux worker process maximum only; container cgroup limit covers its total.',
        'limits': ['Retrospective original PCA, centered smoothing and public exposure remain.',
                   'Eight people are dependent clusters; cells and fits are not independent subjects.',
                   'This trusted route does not qualify arbitrary participant execution.']}
    body = encoded(result)
    need(total_output+len(body) <= protocol['output_limit'], 'Final result fits full operation output limit')
    put(output/'RESULT.json', body, 1024*1024)
    return {'status': result['status'], 'cells': 42, 'fits': fits, 'result': pin(body)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True)
    args = parser.parse_args()
    p = json.loads(Path(args.protocol).read_text())
    need(p['schema'] == 'language-fixed-trusted-operator-inner/v1' and p['expected_fits'] == 5685,
         'Fixed complete original operation')
    result = run(p, Path('/source/implementations'), Path('/store'), Path('/provided/REFERENCE.json'), Path('/output'))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
