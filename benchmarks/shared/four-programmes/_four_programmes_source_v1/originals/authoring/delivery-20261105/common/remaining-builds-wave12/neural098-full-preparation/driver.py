"""Complete33 preparation orchestration. No native work occurs at import.

run() is called only by the selected worker after runtime/source preflight.
Tests inject a tiny library at its explicit native boundary.
"""
import json
import os
from pathlib import Path
import sys
import time

from custody import need, below, capture_file, read_pinned, hash_staged, write_exclusive
from source_plan import encode, digest, validate
from native_io import NativeIO
from native_capture import capture_person, verify_gap_horizons
from epoch_guard import Guard
from scientific_source import load
from publication import Publisher

MAXIMA = {'max_files': 4096, 'max_source_bytes': 128 * 2**30, 'max_runs': 2112,
          'max_events': 1000000, 'max_retained': 100000, 'max_raw_samples': 20000000}


def limits(value):
    need(type(value) is dict and set(value) == set(MAXIMA), 'exact full preparation caps')
    for key, cap in value.items():
        need(type(cap) is int and 0 < cap <= MAXIMA[key], 'bounded selected ' + key)
    return value


def json_value(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'unique metadata JSON keys'); out[key] = value
        return out
    def invalid(_): raise ValueError('nonfinite metadata')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def directories(root_fd, names):
    """Fresh private source-tree directories, without following existing links."""
    created = set()
    for name in names:
        parts = name.split('/')[:-1]
        for i in range(1, len(parts) + 1):
            parent = '/'.join(parts[:i])
            if parent in created: continue
            if i == 1: os.mkdir(parent, 0o700, dir_fd=root_fd)
            else:
                fd = below(root_fd, '/'.join(parts[:i - 1]), os.O_RDONLY | os.O_DIRECTORY)
                try: os.mkdir(parts[i - 1], 0o700, dir_fd=fd)
                finally: os.close(fd)
            created.add(parent)
    return created


def run(*, plan, caps, profile, source_root_fd, work, work_fd, budget, bridge,
        terminal, scientific_raw, library, native_context=NativeIO):
    """No subset success: any source/support/consumer failure retains evidence."""
    caps = limits(caps)
    need(profile in bridge.PROFILES, 'explicit original or nullable-next binding ABI')
    info = validate(plan, bridge.PEOPLE, caps)
    for name in ('stage', 'evidence', 'public'):
        os.mkdir(name, 0o700, dir_fd=work_fd)
    stage_fd = evidence_fd = output_fd = None
    guard = None; phase = 'stage'; completed = []
    try:
        stage_fd = below(work_fd, 'stage', os.O_RDONLY | os.O_DIRECTORY)
        evidence_fd = below(work_fd, 'evidence', os.O_RDONLY | os.O_DIRECTORY)
        output_fd = below(work_fd, 'public', os.O_RDONLY | os.O_DIRECTORY)
        stage = Path(work) / 'stage'
        nested = directories(stage_fd, info['files'])
        snapshots = [capture_file(source_root_fd, stage_fd, row, budget) for row in info['files'].values()]
        signatures = {v['path']: v['stage_signature'] for v in snapshots}
        for name in sorted(nested, key=lambda p: -p.count('/')):
            fd = below(stage_fd, name, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        os.fsync(stage_fd)
        snapshot_pin = write_exclusive(evidence_fd, 'SNAPSHOT.json', encode(snapshots), budget, 4_000_000)
        identities = {}; histories = {}; observation_bytes = {}; declared = {}; events = retained = total_observation = 0
        with native_context(stage=stage, stage_fd=stage_fd, files=info['files'], stage_signatures=signatures,
                            budget=budget, fiff_module=library.fiff_module, raw_module=library.raw_module) as native:
            for person in bridge.PEOPLE:
                phase = 'observe:' + person; budget.check()
                item = plan['participants'][person]
                history_raw = read_pinned(stage_fd, item['history'], budget, 4_000_000,
                                         expected_signature=signatures[item['history']['path']])
                history = json_value(history_raw)
                need(type(history) is dict and bool(history), 'selected nonempty actual preprocessing history')
                histories[person] = history
                roster_raw = encode(item); roster = {'bytes': len(roster_raw), 'sha256': digest(roster_raw)}
                remaining = dict(caps, max_events=caps['max_events'] - events, max_retained=caps['max_retained'] - retained)
                observation, identity = capture_person(library, person=person, item=item, stage=stage,
                    source_roster_pin=roster, history_sha256=digest(history_raw), bridge=bridge, caps=remaining, budget=budget)
                events += len(observation['concatenated_events']); retained += len(observation['epochs']['selection'])
                need(events <= caps['max_events'] and retained <= caps['max_retained'], 'cumulative whole33 native capture')
                raw = encode(observation); total_observation += len(raw)
                need(total_observation <= 127_000_000, 'whole bridge input reservation before next person')
                pin = write_exclusive(evidence_fd, person + '.observation.json', raw, budget, 128_000_000)
                observation_bytes[person] = raw; identities[person] = identity
                declared[person] = {'observation': {k: pin[k] for k in ('bytes', 'sha256')},
                    'source_roster': roster, 'run_ids': [v['run'] for v in item['runs']]}
                completed.append(person)
            manifest = encode({'schema': 'neural098-binding-observation-manifest-v1', 'participants': declared})
            phase = 'full33 binding export'
            try:
                binding_result = bridge.export_panel(manifest_raw=manifest, expected_manifest_sha256=digest(manifest),
                    person_raw=observation_bytes, profile=profile,
                    limits={'max_input_bytes': 128000000, 'max_events': caps['max_events'],
                        'max_retained': caps['max_retained'], 'max_runs': caps['max_runs'], 'max_output_bytes': 128000000},
                    deadline_monotonic=min(budget.deadline, time.monotonic() + 599.0))
            except bridge.BindingFailure as original_failure:
                # These are partial operator evidence, never a public packet.
                # Failure publication uses the same remaining original budget.
                try:
                    write_exclusive(evidence_fd, 'BINDING_FAILURE.json', encode(original_failure.report), budget, 65536)
                    for failed_person, body in original_failure.completed_bindings.items():
                        need(failed_person in bridge.PEOPLE, 'known partial binding participant')
                        write_exclusive(evidence_fd, failed_person + '.partial.bindings.json', body, budget, 32_000_000)
                except BaseException as retention_error:
                    if not isinstance(retention_error, Exception): raise
                    raise original_failure from retention_error
                raise
            write_exclusive(evidence_fd, 'BINDING_RECEIPT.json', binding_result['receipt'], budget, 4_000_000)
            write_exclusive(evidence_fd, 'OBSERVATION_MANIFEST.json', manifest, budget, 1_048_576)
            guard = Guard(library=library, people=bridge.PEOPLE, plan=plan, identities=identities,
                stage=stage, stage_fd=stage_fd, files=info['files'], signatures=signatures, caps=caps, budget=budget)
            binding_lookup = {}
            def read_binding(path, expected):
                need(path in binding_lookup, 'operator-only selected binding input')
                body = binding_lookup[path]
                need(len(body) <= 32_000_000 and digest(body) == expected, 'complete binding capture')
                return json_value(body), expected
            publisher = None
            def checkpoint(person, rows, block): publisher.checkpoint(person, rows, block)
            def forbidden_write(*a, **k): raise ValueError('original publication seam not isolated')
            scientific = load(prepare_raw=scientific_raw['prepare'], protocol_raw=scientific_raw['protocol'],
                reference_raw=scientific_raw['reference'], terminal_generator=terminal, profile=profile,
                io_hooks={'source_pin': guard.source_pin, 'read_json': read_binding, 'write_json': forbidden_write,
                          'checkpoint': checkpoint}, native_proxy=guard)
            publisher = Publisher(np=library.np, output_fd=output_fd, evidence_fd=evidence_fd,
                                  budget=budget, scientific=scientific, people=list(bridge.PEOPLE))
            canonical = {'schema': 'neural098-source-plan-v1', 'participants': {}}
            for person in bridge.PEOPLE:
                phase = 'bind:' + person
                body = binding_result['bindings'][person]; binding = json_value(body)
                observation = json_value(observation_bytes[person])
                verify_gap_horizons(observation, binding, identities[person]['raw_gap_intervals'], scientific, budget)
                pin = write_exclusive(evidence_fd, person + '.bindings.json', body, budget, 32_000_000)
                key = str(Path(work) / 'evidence' / pin['path']); binding_lookup[key] = body
                item = plan['participants'][person]; primary = item['epochs']['parts'][0]
                canonical['participants'][person] = {'epochs_path': str(stage / primary['path']),
                    'epochs_bytes': primary['bytes'], 'epochs_sha256': primary['sha256'],
                    'events_path': key, 'events_sha256': pin['sha256'], 'preprocessing_provenance': histories[person]}
            write_exclusive(evidence_fd, 'NATIVE_IDENTITIES.json', encode(identities), budget, 128_000_000)
            phase = 'complete original window/support preparation'
            rows, blocks, provenance = scientific['prepare'](canonical, Path(work) / 'original-unpublished', list(bridge.PEOPLE))
            guard.complete()
            phase = 'public consumer domain and support'
            result = publisher.publish(rows, blocks, provenance)
            phase = 'complete staged source post-read custody'
            for row in info['files'].values():
                hash_staged(stage_fd, row, signatures[row['path']], budget)
        # The context must finish closure/restoration before completion exists.
        budget.check()
        native_record = {'opened': native.opened_count, 'closed': native.closed_count}
        result.update({'schema': 'neural098-full33-native-preparation-v1', 'complete_preparation': True,
            'profile': profile, 'source_plan_sha256': digest(encode(plan)), 'snapshot_pin': snapshot_pin,
            'native_handles': native_record, 'source_derivation': scientific['source_derivation'],
            'all33_people_preserved': True, 'all_retained_bindings_preserved': True,
            'numeric_window_preparation_only': True, 'candidate_or_model_or_reference_or_scorer_executed': False,
            'participant_identity_proven_by_hashes': False, 'historical_native_parity': False,
            'scientific_qualification': False, 'outer_natural_exit_pending': True,
            'managed_read_bytes': budget.read, 'managed_write_bytes_before_completion': budget.write})
        phase = 'durable final completion'
        os.fsync(output_fd); os.fsync(evidence_fd); os.fsync(stage_fd); os.fsync(work_fd)
        budget.check()
        completion = write_exclusive(work_fd, 'COMPLETION.json', encode(result), budget, 4_000_000)
        os.fsync(work_fd); budget.check()
        return completion
    except BaseException as original:
        failure = {'schema': 'neural098-preparation-failure-v1', 'complete_preparation': False,
                   'phase': phase, 'error': type(original).__name__, 'observed_people': completed,
                   'managed_read_bytes': budget.read, 'managed_write_bytes': budget.write}
        if isinstance(original, Exception) and evidence_fd is not None:
            try: write_exclusive(evidence_fd, 'FAILURE.json', encode(failure), budget, 65536)
            except Exception: pass  # Deadline/cap failures may leave only already closed evidence.
        raise
    finally:
        original = sys.exception(); errors = []
        if guard is not None:
            try: guard.close_active()
            except BaseException as exc: errors.append(exc)
        for fd in (output_fd, evidence_fd, stage_fd):
            if fd is not None:
                try: os.close(fd)
                except BaseException as exc: errors.append(exc)
        if errors:
            if original is not None and not isinstance(original, Exception): raise original
            raise errors[0] from original
        if original is None: budget.check()
