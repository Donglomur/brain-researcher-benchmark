"""Full two-artifact producer, closure barrier, then guarded investigation grade."""
import os
from pathlib import Path
import signal
import time
import policy
import native
import grading


def write(path, value, cap, budget):
    return c.save(path, c.encoded(value), cap, budget.tick, budget.write)


def dependencies(package, binding, budget):
    """Only metadata/public source selection here; never scan private data bodies."""
    package = c.path(package)
    expected = binding['export_pin']
    export = c.parse(c.capture(package / 'DELIVERY_MANIFEST.json', 100000, expected,
                              budget.tick, budget.read))
    rows = binding['files']
    c.need(len(rows) == 182 and len({r['target'] for r in rows}) == 182,
           'Complete unchanged182 metadata')
    c.need(export['task_ids'] == ['NEURAL-100'] and export['files'] == rows,
           'Exact accepted export metadata')
    for row in rows:
        path = Path(row['target'])
        c.need(not path.is_absolute() and '..' not in path.parts
               and path.parts[0] in ('public', 'private'), 'Bounded export-relative name')
    public = [r for r in rows if r['visibility'] == 'public']
    c.need(len(public) == 54 and sum(r['bytes'] for r in public) == 22629836
           and sum(r['target'].endswith('.npz') for r in public) == 47,
           'Complete54 public members /47 primitive inputs')
    return package, public


def prepare(package, public, root, budget):
    current = root / 'current'
    c.need(not os.path.lexists(current), 'Fresh complete public view')
    budget.capacity(23000000)
    current.mkdir(mode=0o755)
    expected = {}
    for row in public:
        rel = Path(row['target']).relative_to('public')
        target = current / rel
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        raw = c.capture(package / row['target'], 23000000, c.only_pin(row), budget.tick, budget.read)
        expected[rel.as_posix()] = c.save(target, raw, 23000000, budget.tick, budget.write)
        c.readable(target, budget.tick)
    files, dirs, used = c.inventory(current, 23000000, 70)
    c.need(set(files) == set(expected), 'Only54 public members')
    for directory in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        c.sync_dir(directory, budget.tick)
    c.sync_dir(root, budget.tick)
    for name, (path, _) in files.items():
        c.capture(path, 23000000, expected[name], budget.tick, budget.read)
    roster = c.parse(c.capture(current / 'ROSTER.json', 65536, expected['ROSTER.json'],
                               budget.tick, budget.read))
    grading.roster_admit(roster)
    prepared = write(root / 'VIEW_PREPARED.json', {
        'schema': 'neural100_investigation_public_view_v1', 'files': expected,
        'member_count': 54, 'primitive_files': 47, 'allocated_bytes': used,
        'signals_decoded': False}, 32768, budget)
    return current, expected, prepared, roster


def retire(current, expected, root, budget):
    files, dirs, _ = c.inventory(current, 23000000, 70)
    c.need(set(files) == set(expected), 'Exact owned view before retirement')
    for name, (path, _) in files.items():
        c.capture(path, 23000000, expected[name], budget.tick, budget.read)
    write(root / 'VIEW_RETIRE_INTENT.json', {'files': expected,
          'after_candidate_native_closure': True}, 32768, budget)
    for path, identity in files.values():
        budget.tick()
        c.need(c.stamp(path.lstat()) == identity, 'Same owned retired inode')
        path.unlink()
        c.sync_dir(path.parent, budget.tick)
    for directory in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        directory.rmdir()
        c.sync_dir(directory.parent, budget.tick)
    c.need(not os.path.lexists(current), 'Whole public view absent')
    return write(root / 'VIEW_RETIRED.json', {'schema': 'neural100_investigation_retirement_v1',
                 'member_count': 54, 'primitive_files': 47, 'absent': True,
                 'parent_fsynced': True}, 8192, budget)


def phase_admit(value, role, source, names):
    c.need(type(value) is dict and value.get('phase') == role
           and value.get('source') == source and value.get('status') == 'captured',
           'Actual selected native phase identity')
    for key in ('all_native_resources_closed', 'cli_reaped', 'producer_closed_before_capture'):
        c.need(value.get(key) is True, 'Positive native closure: ' + key)
    c.validate_natural_exit(value.get('natural_exit'))
    c.need(type(value.get('outputs')) is dict and set(value['outputs']) == set(names),
           'Exact captured phase outputs')
    for pin in value['outputs'].values():
        c.exact_pin(pin)


def run(s, sources, *, phase=None, np=None):
    """Real native leaves by default; injected inert leaves are engineering-only."""
    policy.selection(s, sources.identity)
    phase = native.phase if phase is None else phase
    started = time.monotonic()
    end = started + s['whole_seconds']
    root = c.path(s['output'])
    budget = c.Budget(root, s['other_future_bytes'], end)
    policy.reviews(s, budget)  # Before constructing Docker or preparing signal input.
    c.need(not os.path.lexists(root) and root.parent.is_dir(), 'Fresh custody root')
    package = c.path(s['data_package'])
    c.need(not root.is_relative_to(package) and not package.is_relative_to(root)
           and not root.is_relative_to(sources.root) and not sources.root.is_relative_to(root),
           'Disjoint source/data/custody')
    budget.capacity()
    budget.read(sum(len(raw) + 1 for raw in sources.raw.values()) + 65536)
    package, public = dependencies(package, sources.data, budget)
    program = c.capture(s['program']['path'], 131072, c.only_pin(s['program']), budget.tick, budget.read)
    c.need('\0' not in program.decode('utf-8'), 'Frozen self-contained UTF8 programme')
    if np is None:
        import numpy as np
    c.need(np.__version__ == s['host_numpy_version'], 'Selected host support-admission NumPy')
    root.mkdir(mode=0o700)
    for name in ('commitment', 'candidate', 'grade'):
        (root / name).mkdir(mode=0o700)
    c.sync_dir(root, budget.tick)
    c.sync_dir(root.parent, budget.tick)
    here = root / 'commitment'
    # Grade receives an immutable captured source capsule, never mutable authoring imports.
    for name, raw in sources.raw.items():
        target = here / name
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        c.save(target, raw, 1048576, budget.tick, budget.write)
        c.readable(target, budget.tick)
    source_raw = c.capture(sources.root / 'SOURCE_MANIFEST.json', 65536, sources.identity,
                           budget.tick, budget.read)
    c.save(here / 'SOURCE_MANIFEST.json', source_raw, 65536, budget.tick, budget.write)
    c.readable(here / 'SOURCE_MANIFEST.json', budget.tick)
    frozen = c.save(here / 'program.py', program, 131072, budget.tick, budget.write)
    c.readable(here / 'program.py', budget.tick)
    os.chmod(here, 0o755)
    c.sync_dir(here, budget.tick)
    commitment = write(root / 'COMMITMENT.json', {'schema': 'neural100_investigation_commitment_v1',
        'source': sources.identity, 'program': frozen, 'scope': grading.SCOPE,
        'method_review': c.only_pin(s['method_review']), 'before_any_public_signal_view': True,
        'candidate_outputs': ['report.json', 'claims.json'], 'feedback_withheld': True}, 8192, budget)
    stage = 'committed'
    try:
        current, expected, prepared, roster = prepare(package, public, root, budget)
        stage = 'candidate'
        budget.native('candidate')
        candidate = phase(s, here, current, here / 'program.py', root / 'candidate',
                          'candidate', sources.identity, budget, end - s['grade_seconds'] - 500,
                          sources.data['export_pin']['sha256'])
        phase_admit(candidate, 'candidate', sources.identity, grading.OUTPUT_CAPS)
        c.capture(here / 'program.py', 131072, frozen, budget.tick, budget.read)
        retirement = retire(current, expected, root, budget)
        stage = 'closed_candidate'
        raw = {name: c.capture(root / 'candidate' / name, cap, candidate['outputs'][name],
                              budget.tick, budget.read)
               for name, cap in grading.OUTPUT_CAPS.items()}
        native_pin = c.pin(c.capture(root / 'candidate/NATIVE.json', 262144,
                                    tick=budget.tick, charge=budget.read))
        closure = {'schema': 'neural100_investigation_closed_candidate_v1', 'task_id': 'NEURAL-100',
                   'source': sources.identity, 'program': frozen, 'scope': grading.SCOPE,
                   'artifacts': {name: c.pin(body) for name, body in raw.items()},
                   'native_record': native_pin, 'view_retirement': retirement,
                   'producer_natural_exit': candidate['natural_exit'], 'producer_resources_closed': True,
                   'producer_closed_before_capture': True, 'cli_groups_reaped': True,
                   'all_public_views_retired': True, 'complete_artifacts_captured': True,
                   'numerical_grading_performed': False, 'scientific_qualified': False,
                   'chronology_is_operator_observed': True}
        # Both actual captured bodies + closure pass before grade native construction.
        grading.admit_pair(raw['report.json'], raw['claims.json'], closure, sources.identity, roster, np)
        closure_pin = write(root / 'candidate/CLOSURE.json', closure, 8192, budget)
        for name in (*grading.OUTPUT_CAPS, 'CLOSURE.json'):
            c.readable(root / 'candidate' / name, budget.tick)
        stage = 'both_artifacts_admitted'
        budget.native('grade')
        graded = phase(s, here, package, root / 'candidate', root / 'grade', 'grade',
                       sources.identity, budget, end - 100, sources.data['export_pin']['sha256'])
        phase_admit(graded, 'grade', sources.identity, ('grade.json',))
        value = c.parse(c.capture(root / 'grade/grade.json', 2000000, graded['outputs']['grade.json'],
                                  budget.tick, budget.read))
        c.need(value.get('schema') == 'neural100_investigation_grade_v1'
               and value.get('status') == 'compared_unqualified' and value.get('scope') == grading.SCOPE
               and value.get('source') == sources.identity
               and value.get('export_manifest_sha256') == sources.data['export_pin']['sha256']
               and value.get('candidate_closure') == closure_pin
               and type(value.get('independent_reference_calls')) is int
               and value['independent_reference_calls'] == 1
               and value.get('same_full_reference_for_both_outputs') is True
               and value.get('candidate_claims_used_as_truth') is False
               and value.get('scientific_qualified') is False and value.get('runtime_qualified') is False,
               'Selected complete guarded-grade result')
        for name, body in raw.items():
            c.capture(root / 'candidate' / name, grading.OUTPUT_CAPS[name], c.pin(body), budget.tick, budget.read)
        result = {'schema': 'neural100_investigation_complete_v1', 'status': 'complete_unqualified',
                  'source': sources.identity, 'program': frozen, 'scope': grading.SCOPE,
                  'commitment': commitment, 'prepared_view': prepared, 'retired_view': retirement,
                  'candidate_outputs': closure['artifacts'], 'candidate_closure': closure_pin,
                  'grade_output': graded['outputs']['grade.json'], 'numerical_grading_performed': True,
                  'claims_grading_performed': True, 'scientific_qualified': False,
                  'runtime_qualified': False, 'external_natural_zero_required': True,
                  'source_entry_not_hostile_code_or_identity_proof': True, 'costs': budget.record()}
        write(root / 'COMPLETE.json', result, 32768, budget)
        return result
    except BaseException as exc:
        try:
            write(root / 'FAILURE.json', {'schema': 'neural100_investigation_failure_v1',
                'stage': stage, 'error_type': type(exc).__name__, 'partial_outputs_preserved': True,
                'automatic_retry': False, 'scientific_qualified': False, 'costs': budget.record()}, 16384, budget)
        except BaseException:
            pass
        raise
