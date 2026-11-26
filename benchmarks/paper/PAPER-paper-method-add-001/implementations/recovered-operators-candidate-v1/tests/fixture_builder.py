"""Pure-stdlib generated-input serialization; never loads an operator or NumPy.

This is a software fixture, not source data, native output or a scientific run.
The CLI performs only the separately admitted one-shot sizing operation.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import struct

MIB = 1048576
TOTAL_CAP = 64 * MIB
REQUEST_CAP = 4 * MIB
SOURCE_CAPTURE_CAP = 16 * MIB
FILE_CAP = 10000
DEPTH_CAP = 32
MEASUREMENT_RESERVE = 4 * MIB
EXTERNAL_MEASUREMENT_RESERVE = MIB
METHODS = ('Static decoder', 'Aligned FA', 'ADAN', 'NoMAD', 'Candidate')
GROUPS = ('F3_F4/isometric', 'F3_F4/reaching')
TARGET = ((-3.0, -6.0), (-1.0, -2.0), (1.0, 2.0), (3.0, 6.0))
MUTATIONS = (
    'missing_pair_fact', 'duplicate_pair_fact', 'missing_anchor_selector',
    'duplicate_anchor_reference', 'wrong_anchor_role', 'candidate_profile_mismatch',
    'product_id_alias', 'candidate_label_collision', 'missing_candidate_panel',
    'query_support_mismatch', 'anchor_sample_mismatch', 'anchor_axis_mismatch',
    'failed_and_nonfinite',
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def identifier(value):
    require(type(value) is str and 0 < len(value) <= 32 and value.isascii()
            and all(32 <= ord(c) < 127 for c in value), 'bounded ASCII fixture identifier')
    return value


def relative(value):
    require(type(value) is str and value.isascii() and len(value) <= 64, 'bounded relative path')
    path = PurePosixPath(value)
    require(value and not path.is_absolute() and str(path) == value
            and not set(path.parts) & {'.', '..'} and '\\' not in value,
            'canonical fixture relative path')
    return value


def json_shape(value, depth=0, counter=None):
    if counter is None:
        counter = [0]
    counter[0] += 1
    require(counter[0] <= 2000000 and depth <= DEPTH_CAP, 'JSON node/depth bound')
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        require(abs(value) < 2 ** 63, 'bounded JSON integer')
        return
    if type(value) is float:
        require(math.isfinite(value), 'finite JSON scalar')
        return
    if type(value) is str:
        require(value.isascii() and len(value) <= 1024, 'bounded ASCII JSON string')
        return
    require(type(value) in (dict, list, tuple), 'ordinary JSON value')
    require(len(value) <= 10000, 'JSON collection bound')
    if type(value) is dict:
        for key, item in value.items():
            require(type(key) is str, 'JSON text key')
            json_shape(key, depth + 1, counter)
            json_shape(item, depth + 1, counter)
    else:
        for item in value:
            json_shape(item, depth + 1, counter)


def packed_json(value):
    json_shape(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def array_body(values):
    require(len(values) == 4 and all(len(row) == 2 for row in values), 'fixture array shape')
    return struct.pack('<8d', *(float(x) for row in values for x in row))


def selection(document, document_pin, keys, mode):
    return {'schema': 'nomad_statistical_selection_v1',
            'selection_id': 'generated-' + document, 'mode': mode,
            'bindings': {key: {'document': document, 'pin': document_pin, 'pointer': [key]}
                         for key in keys}}


def build(output, numpy_version, source_capture_bytes, *, scenario='baseline',
          mutation=None, original_mode=False, reverse_products=False):
    """Serialize one complete fixture; invalid cases are explicit test mutations.

    All payloads, including the request and measurement, are bounded in memory
    before the first filesystem write. No runtime source is read or imported.
    """
    identifier(numpy_version)
    require(type(source_capture_bytes) is int and 0 < source_capture_bytes <= 512 * 1024,
            'explicit bounded manifest-plus-source capture bytes')
    require(scenario in ('baseline', 'equal', 'median_trap'), 'known generated scenario')
    require(mutation is None or mutation in MUTATIONS, 'known generated mutation')
    require(type(original_mode) is bool and type(reverse_products) is bool, 'explicit fixture mode')
    output = Path(output).absolute()
    require(len(str(output)) <= 1024 and str(output).isascii(), 'bounded ASCII output path')
    require(not output.exists() and output.parent.is_dir(), 'exclusive output with existing parent')
    require(not any(p.is_symlink() for p in (output, *output.parents)), 'ordinary output ancestry')
    raw_files = {}
    ordinary = {}
    protected = {}
    document_objects = {}

    def add_raw(name, path, raw, *, target=False, cap=MIB):
        identifier(name)
        relative(path)
        require(type(raw) is bytes and len(raw) <= cap, 'bounded literal fixture body')
        full = ('protected/' if target else 'ordinary/') + path
        relative(full)
        require(full not in raw_files, 'distinct fixture file path')
        raw_files[full] = raw
        table = protected if target else ordinary
        require(name not in table, 'distinct catalog name')
        table[name] = {'path': path, **pin(raw)}
        return table[name]

    def add_document(name, path, value, *, target=False, cap=MIB):
        raw = packed_json(value)
        desc = add_raw(name, path, raw, target=target, cap=cap)
        if not target:
            document_objects[name] = value
        return desc

    def replace_document(name, value, cap=MIB):
        raw = packed_json(value)
        require(len(raw) <= cap, 'mutated JSON extent')
        path = ordinary[name]['path']
        raw_files['ordinary/' + path] = raw
        ordinary[name] = {'path': path, **pin(raw)}
        document_objects[name] = value

    def replace_array(name, values):
        raw = array_body(values)
        path = ordinary[name]['path']
        raw_files['ordinary/' + path] = raw
        ordinary[name] = {'path': path, **pin(raw)}

    origin = {'schema': 'generated_nomad_fixture_v1', 'scope': 'software-inputs-only',
              'native_execution': False, 'authentic_data': False}
    origin_desc = add_document('origin', 'origin.json', origin)
    source_pin = {key: origin_desc[key] for key in ('bytes', 'sha256')}
    profiles = {}
    for mi, method in enumerate(METHODS):
        identifier(method)
        desc = add_document('mp' + str(mi), 'mp' + str(mi) + '.json',
                            {'schema': 'generated_method_profile_v1', 'method': method,
                             'source_pin': source_pin, 'native_execution': False,
                             'reference_policy': 'method-scoped-generated'})
        profiles[method] = {'label': method,
                            'profile_pin': {key: desc[key] for key in ('bytes', 'sha256')}}

    supports = {}
    products = []
    slots = []
    target_number = 0
    for task, prefix, count in (('isometric', 'i', 20), ('reaching', 'r', 12)):
        sessions = [identifier(prefix + str(i).zfill(2)) for i in range(count)]
        group = {'unit_id': task, 'source_support_pin': source_pin, 'reference_day': None,
                 'pairs': [], 'test_pair_ids': [], 'evaluation_order': None,
                 'summary_products': {method: {'anchors': [], 'calibration': [],
                                              'first_evaluation': []} for method in METHODS},
                 'calendar': None}
        axes = ['x', 'y']
        units = ['generated-force', 'generated-force'] if task == 'isometric' else [
            'generated-velocity', 'generated-velocity']
        endpoints = [('query', ref, query) for ref in sessions for query in sessions if ref != query]
        endpoints += [('anchor', ref, ref) for ref in sessions]
        for pair_index, (role, ref, query) in enumerate(endpoints):
            pair_id = identifier(prefix + '-' + ref + '-' + query)
            sample_ids = [identifier(pair_id + '-s' + str(i)) for i in range(4)]
            tname = identifier('t' + str(target_number))
            tsname = identifier('ts' + str(target_number))
            target_number += 1
            target_desc = add_raw(tname, tname + '.f64', array_body(TARGET), target=True, cap=64)
            tsdesc = add_document(tsname, tsname + '.json',
                                 {'sample_ids': sample_ids, 'axis_ids': axes, 'axis_units': units},
                                 target=True, cap=512)
            target_pin = {key: target_desc[key] for key in ('bytes', 'sha256')}
            target_support_pin = {key: tsdesc[key] for key in ('bytes', 'sha256')}
            pair = {'pair_id': pair_id, 'reference_id': ref, 'query_id': query,
                    'day_gap': int(query[1:]) - int(ref[1:]),
                    'target_support_pin': target_support_pin, 'products': {}}
            for mi, method in enumerate(METHODS):
                number = len(products)
                pid = identifier(prefix + '-' + role[0] + str(pair_index) + '-m' + str(mi))
                sname, pname, lname = ('s' + str(number), 'p' + str(number), 'l' + str(number))
                error = (2.0, 1.5, 1.25, 1.0,
                         0.5 if task == 'isometric' else 1.5)[mi]
                if scenario == 'equal' and method == 'Candidate':
                    error = 1.0
                if scenario == 'median_trap' and method in ('NoMAD', 'Candidate'):
                    error = (0.0 if pair_index % 3 == 0 else 1.0) if method == 'NoMAD' else (
                        0.0 if pair_index % 3 in (0, 1) else 1.0)
                values = [[x + error for x in row] for row in TARGET]
                pred = add_raw(pname, pname + '.f64', array_body(values), cap=64)
                lineage = {'schema': 'generated_prediction_lineage_v1', 'method': method,
                           'reference_id': ref, 'query_id': query, 'axis_units': units,
                           'method_profile_pin': profiles[method]['profile_pin'],
                           'source_pin': source_pin, 'native_capture': False,
                           'scope': 'generated-grade-inputs-only',
                           'reference_path': 'separate-generated-arm',
                           'role': role}
                lin = add_document(lname, lname + '.json', lineage, cap=4096)
                support = {
                    'schema': 'nomad_prediction_support_v1', 'product_id': pid,
                    'task': task, 'method': method, 'method_profile_pin': profiles[method]['profile_pin'],
                    'source_pin': source_pin, 'reference_id': ref, 'query_id': query, 'role': role,
                    'sample_ids': sample_ids, 'axis_ids': axes, 'target_support_pin': target_support_pin,
                    'prediction_artifact_pin': {key: pred[key] for key in ('bytes', 'sha256')},
                    'target_artifact_pin': target_pin,
                    'prediction_lineage_pin': {key: lin[key] for key in ('bytes', 'sha256')},
                    'expected_numpy_version': numpy_version}
                add_document(sname, sname + '.json', support, cap=2048)
                row = {'support': sname, 'prediction': pname, 'shape': [4, 2],
                       'target': tname, 'target_support': tsname, 'lineage': lname,
                       'status': 'complete', 'failure': None}
                products.append(row)
                slots.append({'row': row, 'support': support, 'lineage': lineage,
                              'task': task, 'method': method, 'role': role,
                              'product_id': pid, 'pair_index': pair_index})
                if role == 'query':
                    pair['products'][method] = {'query': pid, 'anchor': None}
                else:
                    group['summary_products'][method]['anchors'].append(pid)
            if role == 'query':
                group['pairs'].append(pair)
                group['test_pair_ids'].append(pair_id)
        supports['F3_F4/' + task] = group

    require(len(products) == 2720 and target_number == 544, 'complete generated slot/target geometry')
    require(sum(s['role'] == 'anchor' for s in slots) == 160, 'all method-specific anchors')
    require(sum(s['role'] == 'anchor' and s['method'] == 'Candidate' for s in slots) == 32,
            'candidate-scoped anchors')
    declaration = {'schema': 'nomad_f3_f4_candidate_arm_v1', 'method': 'Candidate',
                   'baseline_method': 'NoMAD', 'scope': list(GROUPS),
                   'profile_pin': profiles['Candidate']['profile_pin'],
                   'anchor_policy': 'candidate_scoped'}
    facts = {'supports': supports, 'method_profiles': profiles, 'source_pin': source_pin,
             'candidate_arm': declaration}
    cq = next(s for s in slots if s['task'] == 'isometric' and s['method'] == 'Candidate' and s['role'] == 'query')
    ca = next(s for s in slots if s['task'] == 'isometric' and s['method'] == 'Candidate' and s['role'] == 'anchor')
    aa = next(s for s in slots if s['task'] == 'isometric' and s['method'] == 'NoMAD' and s['role'] == 'anchor')
    if mutation == 'missing_pair_fact':
        supports[GROUPS[0]]['pairs'].pop()
        supports[GROUPS[0]]['test_pair_ids'].pop()
    elif mutation == 'duplicate_pair_fact':
        supports[GROUPS[0]]['pairs'][-1] = supports[GROUPS[0]]['pairs'][0]
        supports[GROUPS[0]]['test_pair_ids'][-1] = supports[GROUPS[0]]['test_pair_ids'][0]
    elif mutation == 'missing_anchor_selector':
        products.remove(ca['row'])
    elif mutation == 'duplicate_anchor_reference':
        ca['support']['reference_id'] = ca['support']['query_id'] = 'i01'
        ca['lineage']['reference_id'] = ca['lineage']['query_id'] = 'i01'
    elif mutation == 'wrong_anchor_role':
        ca['support']['role'] = 'query'
    elif mutation == 'candidate_profile_mismatch':
        cq['support']['method_profile_pin'] = profiles['NoMAD']['profile_pin']
    elif mutation == 'product_id_alias':
        ca['support']['product_id'] = aa['support']['product_id']
    elif mutation == 'candidate_label_collision':
        declaration['method'] = 'NoMAD'
    elif mutation == 'missing_candidate_panel':
        del supports[GROUPS[1]]
    elif mutation == 'query_support_mismatch':
        cq['support']['target_support_pin'] = {'bytes': 1, 'sha256': '0' * 64}
    elif mutation == 'anchor_sample_mismatch':
        ca['support']['sample_ids'] = ['different-' + str(i) for i in range(4)]
    elif mutation == 'anchor_axis_mismatch':
        ca['support']['axis_ids'] = ['wrong-x', 'wrong-y']
    elif mutation == 'failed_and_nonfinite':
        row = ca['row']
        fname = 'failure0'
        failure = {'schema': 'nomad_captured_failed_attempt_v2',
                   'product_id': ca['support']['product_id'], 'method': 'Candidate',
                   'session_id': 'isometric', 'block_id': ca['support']['query_id'],
                   'reference_id': ca['support']['reference_id'],
                   'query_id': ca['support']['query_id'], 'role': 'anchor',
                   'exception_type': 'GeneratedFailure'}
        fdesc = add_document(fname, fname + '.json', failure, cap=4096)
        row.update(prediction=None, shape=None, lineage=None, status='failed', failure=fname)
        ca['support']['prediction_artifact_pin'] = None
        ca['support']['prediction_lineage_pin'] = {key: fdesc[key] for key in ('bytes', 'sha256')}
        bad = [[float('nan'), -5.5], [-0.5, -1.5], [1.5, 2.5], [3.5, 6.5]]
        replace_array(cq['row']['prediction'], bad)

    # Re-seal changed support/lineage bytes. Synthetic target descriptor mutations
    # deliberately remain inconsistent so the real archive checks can reject them.
    for slot in slots:
        row = slot['row']
        if row['status'] == 'complete':
            replace_document(row['lineage'], slot['lineage'], cap=4096)
            for field, name in (('prediction_artifact_pin', row['prediction']),
                                ('prediction_lineage_pin', row['lineage'])):
                slot['support'][field] = {key: ordinary[name][key] for key in ('bytes', 'sha256')}
        replace_document(row['support'], slot['support'], cap=2048)
    if reverse_products:
        products.reverse()

    facts_desc = add_document('facts', 'facts.json', facts, cap=MIB)
    mode = 'original' if original_mode else 'test_only'
    fsel = selection('facts', {key: facts_desc[key] for key in ('bytes', 'sha256')},
                     ('supports', 'method_profiles', 'source_pin', 'candidate_arm'), mode)
    add_document('fact_selection', 'fact-selection.json', fsel)
    statistics = {'statistics': {
        'algorithm': 'conditional_sign_midrank_v1', 'difference_arithmetic': 'exact_score_rationals',
        'zero_policy': 'wilcox', 'tie_policy': 'exact_midrank', 'alternative': 'per_roster',
        'all_zero': 'p_one', 'continuity': 'none', 'quantile_policy': 'linear_type7',
        'multiplicity': 'none_report_only', 'scope': 'original_unresolved'}}
    stats_desc = add_document('statistics', 'statistics.json', statistics)
    ssel = selection('statistics', {key: stats_desc[key] for key in ('bytes', 'sha256')},
                     ('statistics',), mode)
    add_document('statistic_selection', 'statistic-selection.json', ssel)
    archive = {'schema': 'nomad_expected_archive_v2', 'scope': 'complete_endpoints',
               'endpoints': ['F3_F4'], 'groups': [], 'facts_selection_pin': pin(packed_json(fsel))}
    add_document('archive_selection', 'archive-selection.json', archive)
    limits = {'input_cells': 10000000, 'items': 10000000, 'integer_bits': 4096,
              'operations': 1000000000, 'metadata_bytes': 32 * 1024 ** 3,
              'copy_bytes': 16 * 1024 ** 3, 'live_bytes': 8 * 1024 ** 3,
              'dp_states': 1, 'json_bytes': 64 * MIB, 'json_nodes': 50000000,
              'identifier_chars': 4096}
    request = {
        'schema': 'nomad_recovered_operator_request_v1', 'action': 'grade', 'operation': 'statistics',
        'arguments': {'fact_documents': {'facts': 'facts'}, 'fact_selection': 'fact_selection',
                      'statistic_documents': {'statistics': 'statistics'},
                      'statistic_selection': 'statistic_selection', 'products': products,
                      'statistical_limits': limits, 'archive_selection': 'archive_selection',
                      't11_replay': None, 't11_evaluation': None},
        'profile_selection': {}, 'input_root': str(output / 'ordinary'), 'artifacts': ordinary,
        'protected_target_root': str(output / 'protected'), 'protected_target_artifacts': protected,
        'destination': str(output / 'grade-result'),
        'io_limits': {'read_bytes': 128 * MIB, 'write_bytes': 128 * MIB, 'max_member_bytes': 64 * MIB},
        'array_limits': {'max_array_elements': 8},
        'numeric_limits': {'max_array_elements': 8, 'cumulative_elements': 1000000,
                           'cumulative_matmul_products': 1000000}}
    request_raw = packed_json(request)
    require(len(request_raw) <= REQUEST_CAP, 'complete fixture request exceeds selected 4 MiB cap')
    require(source_capture_bytes + len(request_raw) <= SOURCE_CAPTURE_CAP, 'complete source/request ceiling')
    raw_files['request.json'] = request_raw
    require(len(raw_files) + 1 <= FILE_CAP, 'whole fixture file-count preflight')
    total_before_measurement = sum(map(len, raw_files.values()))
    require(total_before_measurement + MEASUREMENT_RESERVE + EXTERNAL_MEASUREMENT_RESERVE <= TOTAL_CAP,
            'whole cumulative fixture plus measurement reserve before writing')
    inventory = [{'path': relative(name), **pin(raw)} for name, raw in sorted(raw_files.items())]
    report = {
        'schema': 'nomad_candidate_fixture_serialization_v1', 'status': 'serialized_inputs_only',
        'scenario': scenario, 'mutation': mutation, 'original_mode_branch_fixture': original_mode,
        'reverse_product_order': reverse_products, 'generated_only': True,
        'runtime_source_imported': False, 'grade_executed': False, 'numpy_imported': False,
        'numerical_runtime_selected': False, 'grade_ready': False,
        'authentic_or_native_output': False, 'numpy_version_declaration': numpy_version,
        'source_capture_bytes_declaration': source_capture_bytes,
        'source_plus_request_capture_bytes': source_capture_bytes + len(request_raw),
        'source_capture_ceiling_bytes': SOURCE_CAPTURE_CAP,
        'request': {'path': 'request.json', **pin(request_raw)},
        'request_cap_bytes': REQUEST_CAP, 'expected_slots': 2720, 'request_slots': len(products),
        'expected_anchors': 160, 'candidate_anchors': 32, 'array_shape': [4, 2],
        'prediction_body_bytes': 2720 * 64, 'unique_target_supports': 544,
        'ordinary_catalog_entries': len(ordinary), 'protected_catalog_entries': len(protected),
        'body_bytes_before_measurement': total_before_measurement,
        'measurement_bytes': 0, 'total_file_bytes': 0, 'file_count': len(raw_files) + 1,
        'file_cap': FILE_CAP, 'cumulative_output_cap_bytes': TOTAL_CAP,
        'external_pool_measurement_reserve_bytes': EXTERNAL_MEASUREMENT_RESERVE,
        'declared_ram_bytes': 512 * MIB, 'ram_is_os_enforced': False,
        'limits_checked_before_first_write': True, 'inventory': inventory}
    measurement = b''
    for _ in range(8):
        measurement = packed_json(report)
        report['measurement_bytes'] = len(measurement)
        report['total_file_bytes'] = total_before_measurement + len(measurement)
    measurement = packed_json(report)
    require(report['measurement_bytes'] == len(measurement), 'stable measurement byte count')
    require(len(measurement) <= MEASUREMENT_RESERVE, 'measurement reserve')
    require(total_before_measurement + len(measurement) + EXTERNAL_MEASUREMENT_RESERVE <= TOTAL_CAP,
            'final cumulative fixture plus external measurement bound')
    raw_files['measurement.json'] = measurement

    # This is the first mutation. On I/O failure the partial owned fixture is
    # retained; callers must not automatically retry the admitted sizing pass.
    output.mkdir(mode=0o700)
    (output / 'ordinary').mkdir(mode=0o700)
    (output / 'protected').mkdir(mode=0o700)
    written = 0
    for name, raw in sorted(raw_files.items()):
        target = output / name
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        try:
            os.fchmod(fd, 0o644)
            view = memoryview(raw)
            offset = 0
            while offset < len(view):
                n = os.write(fd, view[offset:])
                require(n > 0, 'complete fixture write')
                offset += n
            written += len(raw)
        finally:
            os.close(fd)
    require(written == report['total_file_bytes'], 'complete planned serialization count')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--numpy-version', required=True)
    parser.add_argument('--source-capture-bytes', required=True, type=int)
    args = parser.parse_args()
    report = build(args.output, args.numpy_version, args.source_capture_bytes)
    print(json.dumps({key: report[key] for key in (
        'schema', 'status', 'request', 'source_plus_request_capture_bytes',
        'body_bytes_before_measurement', 'measurement_bytes', 'total_file_bytes',
        'file_count', 'expected_slots', 'expected_anchors', 'grade_executed',
        'numerical_runtime_selected', 'grade_ready',
        'declared_ram_bytes', 'ram_is_os_enforced')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
