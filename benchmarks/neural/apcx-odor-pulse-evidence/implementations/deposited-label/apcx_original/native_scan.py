"""One complete released APCx Parquet census; no candidate packet or fitted model."""
import base64
from collections import Counter
import math
import resource
import sys

from . import census_core as core
from . import command_audit
from . import shared_commands
from .native_io import MeteredReader, full_digest


def reported_scalars(mapping):
    """Keep ordinary scalars; represent malformed scalar fields explicitly, not as zero."""
    out = {}
    for key, value in mapping.items():
        if value is None or type(value) in (str, int, bool) or (type(value) is float and math.isfinite(value)):
            out[key] = value
        else:
            out[key] = {'invalid_scalar_type': type(value).__name__,
                        'decoded_value_fingerprint': core.fingerprint(value)}
    return out


def check_arrow_schema(pa, schema, limits):
    if len(schema) > limits['max_columns'] or len(set(schema.names)) != len(schema.names):
        raise ValueError('duplicate or excessive top-level columns')
    def field_check(field, depth):
        if depth > 8: raise ValueError('Arrow nesting cap')
        if any(k.startswith(b'ARROW:extension:') for k in (field.metadata or {})):
            raise ValueError('extension metadata not admitted')
        t = field.type
        if isinstance(t, pa.BaseExtensionType): raise ValueError('extension type not admitted')
        if pa.types.is_list(t) or pa.types.is_large_list(t) or pa.types.is_fixed_size_list(t):
            field_check(t.value_field, depth + 1)
        elif pa.types.is_dictionary(t):
            field_check(pa.field('dictionary-value', t.value_type), depth + 1)
        elif not (pa.types.is_null(t) or pa.types.is_boolean(t) or pa.types.is_integer(t)
                  or pa.types.is_floating(t) or pa.types.is_string(t) or pa.types.is_large_string(t)
                  or pa.types.is_binary(t) or pa.types.is_large_binary(t)):
            raise ValueError('unsupported Arrow type; no implicit unit/object conversion: ' + str(t))
    for field in schema: field_check(field, 0)


def schema_report(pa, pf, limits, file_size):
    md = pf.metadata; schema = pf.schema_arrow
    check_arrow_schema(pa, schema, limits)
    if not 0 < md.num_rows <= limits['max_rows'] or not 0 < md.num_row_groups <= limits['max_row_groups']:
        raise ValueError('complete row/rowgroup bound')
    if md.num_columns > limits['max_columns']: raise ValueError('leaf column bound')
    groups = []; declared_decoded = 0; spans = []
    for i in range(md.num_row_groups):
        group = md.row_group(i); columns = []
        for j in range(group.num_columns):
            c = group.column(j)
            if c.file_path: raise ValueError('external column-file reference not admitted')
            if c.total_compressed_size < 0 or c.total_uncompressed_size < 0:
                raise ValueError('invalid declared chunk lengths')
            offsets = [x for x in (c.data_page_offset, c.dictionary_page_offset) if x is not None and x > 0]
            if c.total_compressed_size and not offsets: raise ValueError('column chunk without admitted data offset')
            start = min(offsets) if offsets else 4
            end = start + c.total_compressed_size
            if start < 4 or end > file_size - limits['expected_footer_bytes'] - 8:
                raise ValueError('column chunk outside data extent')
            if c.total_compressed_size: spans.append((start, end))
            declared_decoded += c.total_uncompressed_size
            columns.append({'path': c.path_in_schema, 'compression': c.compression,
                            'values': c.num_values, 'physical_type': c.physical_type,
                            'compressed_bytes': c.total_compressed_size,
                            'declared_uncompressed_bytes': c.total_uncompressed_size,
                            'data_start': start, 'data_end': end})
        groups.append({'index': i, 'rows': group.num_rows, 'columns': columns})
    if any(b[0] < a[1] for a, b in zip(sorted(spans), sorted(spans)[1:])):
        raise ValueError('overlapping Parquet column chunks')
    if declared_decoded > limits['declared_uncompressed_bytes']:
        raise ValueError('declared total native decoded-size cap; no subset fallback')
    return {'rows': md.num_rows, 'row_groups': groups, 'declared_uncompressed_bytes': declared_decoded,
            'schema_arrow': str(schema), 'schema_parquet': str(pf.schema),
            'top_level_fields': list(schema.names),
            'missing_exact_export_fields': sorted(set(core.FIELDS) - set(schema.names)),
            'extra_fields_without_alias_mapping': sorted(set(schema.names) - set(core.FIELDS)),
            'metadata_base64': [{'key': base64.b64encode(k).decode(), 'value': base64.b64encode(v).decode()}
                                for k, v in sorted((md.metadata or {}).items())],
            'pandas_conversion': False, 'extension_deserialization_admitted': False}


def scan_file(pa, pq, source, limits, budget, store):
    sessions = {}; findings = Counter(); count = 0; trial_count = 0; max_pool = 0; expected = dict(source); ungroupable = 0
    command_cache = {}; command_statuses = Counter(); command_issues = Counter(); cache_hits = 0
    reader = MeteredReader(source['path'], source['bytes'], budget)
    pf = None; observed_input_before = None; observed_input_after = None
    try:
        observed_input_before = full_digest(reader)
        if any(observed_input_before[k] != source[k] for k in ('bytes', 'md5', 'sha256')):
            raise ValueError('complete selected input identity')
        reader.seek(0)
        pf = pq.ParquetFile(reader, memory_map=False, buffer_size=0, pre_buffer=False,
            thrift_string_size_limit=1048576, thrift_container_size_limit=100000,
            page_checksum_verification=True, arrow_extensions_enabled=False)
        report = schema_report(pa, pf, limits, source['bytes']); store.json('SCHEMA.json', report)
        expected_names = list(pf.schema_arrow.names)
        layout_scope = limits.get('layout_scope')
        if layout_scope is not None and report['rows'] != layout_scope['rows']:
            raise ValueError('whole immutable release row scope changed')
        with store.line_writer('COMMAND_DIAGNOSTICS.jsonl') as command_out, store.line_writer('ROWS.jsonl') as rows_out:
            # Complete prior census proves one command/legacy value per released
            # trial for this immutable input. Distinct content may be shared by
            # different trials; an unexpected excess refuses the whole operation.
            shared = shared_commands.SharedCommands(command_out,
                layout_scope['trials'] if layout_scope is not None else limits['max_trials'])
            for batch in pf.iter_batches(batch_size=limits['batch_rows'], columns=None,
                                         row_groups=None, use_threads=False, use_pandas_metadata=False):
                budget.check()
                if list(batch.schema.names) != expected_names: raise ValueError('batch schema changed')
                if batch.num_rows > limits['batch_rows'] or batch.nbytes > limits['batch_decoded_bytes']:
                    raise ValueError('decoded batch cap; no partial-row adaptation')
                pool = pa.total_allocated_bytes(); max_pool = max(max_pool, pool)
                if pool > limits['observed_arrow_allocation_bytes']:
                    raise ValueError('observed Arrow allocation exceeded declared soft stop')
                if (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)) > limits['observed_maxrss_bytes']:
                    raise ValueError('observed process high-water RSS exceeded declared soft stop')
                for row in batch.to_pylist():
                    budget.check(); count += 1
                    if count > limits['max_rows']: raise ValueError('full row cap')
                    a = core.audit_row(row, max_elements=limits['max_elements_per_field'])
                    if layout_scope is not None and (type(row.get('Trial odor')) is not list
                            or len(row['Trial odor']) != layout_scope['command_samples']
                            or any(type(v) is not float for v in row['Trial odor'])):
                        raise ValueError('whole immutable command shape changed')
                    budget.charge('logical_scalar_bytes', a['logical_scalar_bytes'])
                    flags = list(a['violations']); identity = a['identity']
                    command_hash = a['field_fingerprints'].get('Trial odor', {}).get('sha256')
                    legacy_hash = core.fingerprint(a['commands_owner_only'])['sha256']
                    # Every row was fully decoded and fingerprinted above. Reuse only
                    # the pure diagnostic for the same complete typed command and legacy digest.
                    command_key = (command_hash, legacy_hash)
                    if command_key in command_cache:
                        diagnostic = command_cache[command_key]; cache_hits += 1
                    else:
                        if len(command_cache) >= limits['max_trials']:
                            raise ValueError('complete command diagnostic cache cap; no subset fallback')
                        diagnostic = command_audit.audit_commands(row.get('Trial odor'),
                            a['commands_owner_only'], command_hash, dict(command_audit.HYPOTHESIS))
                        command_cache[command_key] = diagnostic
                    command_statuses[diagnostic['status']] += 1
                    command_issues.update(diagnostic['issues'])
                    if a['identity_valid_for_released_grouping']:
                        key = (identity['Animal'], identity['Session'])
                        if key not in sessions:
                            if len(sessions) >= limits['max_sessions']: raise ValueError('released session grouping cap')
                            sessions[key] = {'units': set(), 'trials': {}, 'duplicates': 0}
                        s = sessions[key]; tid = identity['Trial']; cell = identity['Cell']; s['units'].add(cell)
                        if len(s['units']) > limits['max_units_per_session']: raise ValueError('released unit grouping cap')
                        if tid not in s['trials']:
                            trial_count += 1
                            if trial_count > limits['max_trials']: raise ValueError('complete released trial grouping cap')
                            s['trials'][tid] = {'units': set(), 'shared_hash': a['trial_shared_fields_sha256'],
                                'first_source_row': count - 1, 'last_source_row': count - 1,
                                'labels_owner_only': reported_scalars(a['labels_owner_only']), 'commands_owner_only': a['commands_owner_only'],
                                'shared_metadata_conflicts': 0, 'command_multiplicity_owner_only': diagnostic}
                        t = s['trials'][tid]
                        if cell in t['units']:
                            s['duplicates'] += 1; flags.append('DUPLICATE_RELEASED_TRIAL_UNIT_ROW')
                        t['units'].add(cell); t['last_source_row'] = count - 1
                        if t['shared_hash'] != a['trial_shared_fields_sha256']:
                            t['shared_metadata_conflicts'] += 1; flags.append('TRIAL_METADATA_DISAGREES_ACROSS_UNITS')
                    else: ungroupable += 1
                    findings.update(flags)
                    expanded_row = {'source_row_zero_based': count - 1, 'identity_owner_only': reported_scalars(identity),
                        'labels_owner_only': reported_scalars(a['labels_owner_only']),
                        'command_conventions_digest': core.fingerprint(a['commands_owner_only'])['sha256'],
                        'command_multiplicity_owner_only': diagnostic,
                        'command_multiplicity_digest': core.fingerprint(diagnostic)['sha256'],
                        'spikes_observed_window': a['spikes'], 'field_shapes': a['field_shapes'],
                        'all_decoded_fields_digest': core.fingerprint(a['field_fingerprints'])['sha256'],
                        'trial_shared_fields_sha256': a['trial_shared_fields_sha256'],
                        'logical_scalar_bytes': a['logical_scalar_bytes'], 'violations': sorted(set(flags)),
                        'candidate_packet': False, 'scientific_primary_admitted': False}
                    rows_out.write(shared.project(expanded_row, 'row', a['identity_valid_for_released_grouping']),
                                   maximum=shared_commands.ROW_RECORD_BYTES)
        if count != report['rows']: raise ValueError('not every metadata-declared row was decoded')
        conclusions = []; by_animal = Counter()
        with store.line_writer('TRIALS.jsonl') as trial_out:
            for (animal, session), s in sorted(sessions.items()):
                by_animal[animal] += 1
                conclusions.append(core.session_conclusion(animal, session, s['trials'], s['units'], s['duplicates']))
                for tid, t in sorted(s['trials'].items()):
                    expanded_trial = {'animal': animal, 'session': session, 'released_trial': tid,
                        **{k: sorted(v) if isinstance(v, set) else v for k, v in t.items()},
                        'original_trial_id_known': False, 'protected_partition_assigned': False}
                    trial_out.write(shared.project(expanded_trial, 'trial', True, allow_new=False),
                                    maximum=shared_commands.TRIAL_RECORD_BYTES)
        store.json('SESSIONS.json', {'complete_released_sessions': conclusions,
                    'reported_name_to_session_counts': dict(by_animal),
                    'expected_count_multiset_only': [12, 13, 17],
                    'paper_name_to_count_correspondence_authenticated': False,
                    'retained_order_source_evidence': 'Exporter masks retain relative input order, then renumbers. Original source chronology and exclusions remain unauthenticated.'})
        layout_report = shared.report()
        if (layout_report['rows'] != count or layout_report['trial_records'] != trial_count
                or layout_report['distinct_released_trial_keys'] != trial_count):
            raise ValueError('complete shared-trial reference closure')
        if layout_scope is not None and (trial_count != layout_scope['trials']
                or len(sessions) != layout_scope['sessions']
                or sum(len(s['units']) for s in sessions.values()) != layout_scope['session_unit_pairs']):
            raise ValueError('whole immutable release grouping scope changed')
        store.json('SHARED_COMMAND_LAYOUT.json', layout_report)
        scope_ok = set(by_animal) == set(core.ANIMALS) and len(sessions) == 42 and sorted(by_animal.values()) == [12, 13, 17]
        holds = list(core.PERMANENT_HOLDS)
        if not scope_ok: holds.append('AVAILABLE_RELEASE_NOT_FULL_THREE_ANIMAL_42_SESSION_COUNT_SCOPE')
        if findings: holds.append('RELEASED_ROW_DISPOSITIONS_REQUIRE_SOURCE_RECONCILIATION')
        if any(s['trial_missing_released_unit_support'] or s['rows_with_duplicate_trial_unit_identity'] for s in conclusions):
            holds.append('RELEASED_UNIT_TRIAL_CARTESIAN_SUPPORT_INCOMPLETE_OR_DUPLICATE')
        if any(not s['conditional_16_8_10_support_gate'] for s in conclusions): holds.append('SOME_RELEASED_SESSIONS_FAIL_CONDITIONAL_SUPPORT_QUOTA')
        store.json('SCIENTIFIC_HOLDS.json', {'holds': holds, 'row_violation_counts': dict(findings),
                   'complete_available_rows_censused': count, 'released_trials': trial_count,
                   'rows_without_groupable_released_identity': ungroupable,
                   'three_animal_42_session_count_scope_matches': scope_ok,
                   'all_original_qc_units_verified': False, 'physical_delivery_target_verified': False,
                   'original_chronology_and_eligibility_verified': False, 'candidate_export_enabled': False})
        command_report = {'complete_rows': count, 'status_counts': dict(command_statuses),
            'issue_row_counts': dict(command_issues), 'unique_complete_command_legacy_digests': len(command_cache),
            'diagnostic_cache_hits': cache_hits, 'original_legacy_row_flags': dict(findings),
            'hypothesis': dict(command_audit.HYPOTHESIS), 'physical_target_verified': False,
            'original_flags_reclassified_or_removed': False, 'scientific_admission': False}
        store.json('COMMAND_RECONCILIATION.json', command_report)
        return {'status': 'COMPLETE_NATIVE_RELEASE_CENSUS_WITH_SCIENTIFIC_HOLDS', 'rows': count,
                'command_reconciliation': command_report, 'shared_command_layout': layout_report,
                'released_sessions': len(sessions), 'released_trials': trial_count,
                'rows_without_groupable_released_identity': ungroupable,
                'release_count_scope_matches': scope_ok, 'holds': holds,
                'max_observed_arrow_allocated_bytes': max_pool, 'all_columns_and_rows_scanned': True,
                'scientific_admission': False, 'models': 0, 'fits': 0,
                'expected_input': expected, 'observed_input_before': observed_input_before}
    finally:
        postflight_identity = None
        try:
            observed_input_after = full_digest(reader)
            if any(observed_input_after[k] != source[k] for k in ('bytes', 'md5', 'sha256')):
                raise ValueError('complete selected input postflight identity')
            postflight_identity = reader.identity()
        finally:
            try:
                if pf is not None: pf.close(force=True)
            finally: reader.close()
        if pf is not None and not pf.closed: raise ValueError('native Parquet reader closure unverified')
        store.json('INPUT_POSTFLIGHT.json', {'full_input_after': observed_input_after,
                    'same_ordinary_file': postflight_identity, 'python_reader_closed': reader.closed,
                    'parquet_reader_closed': bool(pf is not None and pf.closed)})
