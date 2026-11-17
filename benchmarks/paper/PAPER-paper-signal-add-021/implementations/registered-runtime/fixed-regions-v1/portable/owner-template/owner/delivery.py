"""Narrow owner-only delivery for the complete twelve-region TMS profile.

Source preparation is not runtime admission. The accepted Docker owner retains
its historical exact image/socket constants. A fresh operation must independently
admit that source/runtime or review a successor before calling execute_pair.
No reference is a candidate argument or mount. No candidate program runs here.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

from common import admit_pin, decode, encode, need, pin, plain, read, signature, write
import docker_owner

MIB = 1024 * 1024
CAP = 2 * MIB
TASK_ID = 'PAPER-paper-signal-add-021.fixed-regions-v1'
DOCS = ('TASK.md', 'METHOD.json', 'SUBMISSION_SCHEMA.json')
PUBLIC_DOCS = {
    'TASK.md': {'bytes': 2773, 'sha256': 'dc4c933535debdf6e26cbc527665fedf5ecf0dcbed7ad29a843fff2673102d98'},
    'METHOD.json': {'bytes': 6292, 'sha256': 'd0868b617aa4e936319767603c2d34b10275133c21b80250d48fe5302bb709aa'},
    'SUBMISSION_SCHEMA.json': {'bytes': 15889, 'sha256': '1167b43d7b352254b5e04d6f230c9a76b03b5829e461835cbee92edec04f0aac'},
}
PROTECTED_REFERENCE = {'bytes': 359637, 'sha256': 'ceba59b4702c692c4e6819deb5cf72f8d6ebdb68b2a48228caf1860b266f30d8'}
ARMS = {'A': 'paper+data', 'B': 'paper+data+official-code'}
INPUTS = {
    'INPUT.json': {'bytes': 4814, 'sha256': 'a0e3328495f4ba090ba1b2e3b1fe78ed22793ce38a6c78963d9f5637b9b1ab70'},
    'values.f64': {'bytes': 35616000, 'sha256': '93e721d490676f232ae2ac11b065294c0e660f267bcdc466080791c91641264c'},
    'pair_counts.u8': {'bytes': 222600, 'sha256': '6c0d2c0bb833b9bb8efb1ff72400403abbf92882cb5ae1e96322e246f805b4d8'},
    'missingness.json': {'bytes': 1428, 'sha256': 'a2d16bef2777c493df79bbdc83cb058908a6cd28b45723e1a0d11cbd83c61e20'},
}
PAPER = {'bytes': 1996585, 'sha256': '8c8cc3ca22cdeb08459ad3688e86b43b95ef0b052572f319994d1235ae3676fc'}
EXECUTION_LIMITS = {'cpu': 1, 'memory_bytes': docker_owner.MEMORY,
                    'arm_wall_seconds': 120, 'stdout_bytes': CAP,
                    'stderr_bytes': CAP, 'tmpfs_bytes_each': 134217728,
                    'network': 'none', 'regular_file_limit_bytes': MIB}
_TOKEN = object()


def entry_pin(entry, cap):
    need(type(entry) is dict and set(entry) == {'path', 'bytes', 'sha256'}, 'exact_file_selection')
    plain(entry['path'])
    return admit_pin({k: entry[k] for k in ('bytes', 'sha256')}, cap)


def source_name(name):
    need(type(name) is str and name and '\\' not in name, 'relative_code_name')
    path = PurePosixPath(name)
    need(not path.is_absolute() and str(path) == name and all(
        re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', x) and x not in ('.', '..', '__pycache__')
        for x in path.parts), 'code_path_components')
    need(path.suffix.lower() in ('.m', '.py', '.r', '.jl'), 'reviewed_source_only_extension')
    return path


def validate_selection(selection, documents):
    need(type(selection) is dict and set(selection) == {
        'schema', 'task_id', 'root_execution_selected', 'input_files', 'paper',
        'official_code', 'official_code_review', 'programs', 'selected_budget',
        'runtime_admission', 'projection_review'}, 'closed_owner_selection')
    need(selection['schema'] == 'tms_fixed_region_delivery_selection_v1' and
         selection['task_id'] == TASK_ID and selection['root_execution_selected'] is True,
         'root_selected_fixed_region_operation')
    need(type(documents) is dict and set(documents) == set(DOCS), 'exact_public_documents')
    need(all(type(b) is bytes and 0 < len(b) <= 65536 for b in documents.values()), 'public_document_extents')
    need({n: pin(documents[n]) for n in DOCS} == PUBLIC_DOCS, 'exact_reviewed_public_documents')
    need(type(selection['input_files']) is dict and set(selection['input_files']) == set(INPUTS),
         'exact_four_input_files')
    for name, expected in INPUTS.items():
        need(entry_pin(selection['input_files'][name], 40 * MIB) == expected, 'accepted_projection_identity')
    need(entry_pin(selection['paper'], 2 * MIB) == PAPER, 'same_accepted_paper')
    need(type(selection['programs']) is dict and set(selection['programs']) == set(ARMS), 'two_frozen_programs')
    for entry in selection['programs'].values():
        entry_pin(entry, 262144)
    admit_pin(selection['official_code_review'], MIB)
    admit_pin(selection['projection_review'], MIB)
    code = selection['official_code']
    need(type(code) is list and 1 <= len(code) <= 32, 'finite_reviewed_official_allowlist')
    names = set(); total = 0
    for item in code:
        need(type(item) is dict and set(item) == {'relative', 'file'}, 'closed_code_selection')
        name = str(source_name(item['relative']))
        need(name not in names, 'unique_code_names'); names.add(name)
        total += entry_pin(item['file'], 262144)['bytes']
    need(total <= 2 * MIB, 'bounded_code_allowlist_bytes')
    # Exact pin identity binds the pre-reviewed allowlist, not a candidate's assertion.
    need(type(selection['selected_budget']) is dict and selection['selected_budget'] and
         len(encode(selection['selected_budget'])) <= 16384, 'owner_selected_shared_study_budget')
    runtime = selection['runtime_admission']
    need(type(runtime) is dict and set(runtime) == {'image', 'image_content_review', 'daemon_guard_review'} and
         runtime['image'] == docker_owner.IMAGE, 'exact_selected_runtime')
    for key in ('image_content_review', 'daemon_guard_review'):
        admit_pin(runtime[key], MIB)
    # These are custody references to separately accepted root evidence. This
    # adapter does not turn self-authored metadata into a runtime qualification.
    return pin(encode(selection))


def _copy(entry, destination, budget, cap):
    expected = entry_pin(entry, cap)
    body = read(entry['path'], expected, budget, cap=cap)
    write(destination, body, budget)
    return expected


def stage_inputs(root, files, budget):
    """Copy only the four accepted ordinary files, never their provenance folder."""
    need(set(files) == set(INPUTS), 'exact_input_names')
    root = plain(root); root.mkdir(mode=0o700)
    for name, expected in INPUTS.items():
        need(entry_pin(files[name], 40 * MIB) == expected, 'fixed_input_pin')
        _copy(files[name], root / name, budget, 40 * MIB)
    os.chmod(root, 0o500)
    return {'path': str(root), 'files': INPUTS}


def stage_task(root, arm, documents, paper, official_code, budget):
    need(arm in ARMS and set(documents) == set(DOCS), 'exact_arm_documents')
    root = plain(root); root.mkdir(mode=0o700)
    shared = {}
    for name in DOCS:
        need(type(documents[name]) is bytes and len(documents[name]) <= 65536, 'document_limit')
        write(root / name, documents[name], budget); shared[name] = pin(documents[name])
    pdir = root / 'paper'; pdir.mkdir(mode=0o700)
    shared['paper/paper.pdf'] = _copy(paper, pdir / 'paper.pdf', budget, 2 * MIB)
    os.chmod(pdir, 0o500)
    code = {}
    if arm == 'B':
        cdir = root / 'code'; cdir.mkdir(mode=0o700)
        directories = {cdir}
        for item in official_code:
            rel = source_name(item['relative']); target = cdir.joinpath(*rel.parts)
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            directories.update(p for p in target.parents if p == cdir or cdir in p.parents)
            body = read(item['file']['path'], entry_pin(item['file'], 262144), budget, cap=262144)
            need(b'\0' not in body, 'text_source_not_binary'); body.decode('utf-8')
            write(target, body, budget); code[str(rel)] = pin(body)
        for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
            os.chmod(directory, 0o500)
    os.chmod(root, 0o500)
    return {'arm': arm, 'mode': ARMS[arm], 'path': str(root), 'shared': shared, 'code': code}


def shared_binding(selection, documents):
    return {'task_id': TASK_ID, 'documents': {n: pin(documents[n]) for n in DOCS},
            'input_files': INPUTS, 'paper': PAPER,
            'selected_budget': selection['selected_budget'], 'execution_limits': EXECUTION_LIMITS,
            'image': docker_owner.IMAGE,
            'programs': {a: entry_pin(e, 262144) for a, e in selection['programs'].items()},
            'official_code': {i['relative']: entry_pin(i['file'], 262144) for i in selection['official_code']},
            'official_code_review': selection['official_code_review'],
            'projection_review': selection['projection_review'],
            'runtime_admission': selection['runtime_admission']}


def sealed_census(root):
    """Detect added files, aliases, permission changes and host-side mutations.

    Contents were hashed while staging; readonly container mounts cannot mutate
    them. This census closes concurrent ordinary host-edit windows without
    rereading the complete scientific tensor for every arm.
    """
    root = plain(root)
    result = {}
    for path in (root, *sorted(root.rglob('*'))):
        st = path.lstat()
        need(not stat.S_ISLNK(st.st_mode), 'sealed_no_alias')
        if stat.S_ISDIR(st.st_mode):
            need(stat.S_IMODE(st.st_mode) == 0o500, 'sealed_directory')
        else:
            need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and
                 stat.S_IMODE(st.st_mode) == 0o400, 'sealed_ordinary_file')
        result[str(path)] = signature(st)
    return result


@dataclass(frozen=True)
class ClosedSubmission:
    arm: str
    body: object
    binding_bytes: bytes
    lifecycle_pin_bytes: bytes
    status: str
    failure_reason: object
    _token: object


def _freeze(closed, arm, binding, budget):
    docker_owner.require_closed_episode(closed)
    need(arm in ARMS, 'closed_arm')
    life_entry = closed.lifecycle
    life = decode(read(life_entry['path'], entry_pin(life_entry, 262144), budget,
                       cap=262144, mode=0o400), 262144)
    need(life['episode_closed'] is True and life['remaining_owned_cid'] is None,
         'complete_owned_episode_lifecycle')
    if type(closed) is docker_owner.ClosedFailure:
        need(life['candidate_closed'] is False and life['failed_episode_reason'] == closed.reason and
             life['submission'] is None, 'distinct_failed_episode')
        body = None; status = 'execution_failed'; reason = closed.reason
    else:
        need(life['candidate_closed'] is True and life['failure'] is None and
             life['submission'] == closed.submission, 'complete_natural_zero_lifecycle')
        entry = closed.submission
        body = read(entry['path'], entry_pin(entry, CAP), budget, cap=CAP, mode=0o400)
        status = 'completed'; reason = None
    frozen = {'shared': binding, 'arm': arm, 'mode': ARMS[arm],
              'program': binding['programs'][arm], 'submission': None if body is None else pin(body),
              'status': status, 'failure_reason': reason}
    return ClosedSubmission(arm, body, encode(frozen), encode(entry_pin(life_entry, 262144)), status, reason, _TOKEN)


def closed_pair_score(closed, expected_binding, reference_selection, *, scorer, root, budget):
    """The sole reference-read site, reached only after both immutable closures.

    A malformed naturally closed output is scored zero. A separately typed,
    proved closed ordinary candidate failure also scores zero. Infrastructure
    failure, cancellation or uncertain closure cannot pass this barrier.
    """
    need(type(closed) is tuple and len(closed) == 2, 'two_closed_arm_tokens')
    need(type(expected_binding) is dict and type(expected_binding.get('programs')) is dict and
         set(expected_binding['programs']) == set(ARMS), 'expected_two_program_bindings')
    invalid = {}
    commitments = []
    for arm, token in zip(('A', 'B'), closed):
        need(type(token) is ClosedSubmission and token._token is _TOKEN and token.arm == arm,
             'typed_closed_pair')
        need((token.status == 'completed' and type(token.body) is bytes and token.failure_reason is None) or
             (token.status == 'execution_failed' and token.body is None and token.failure_reason in
              ('candidate_timeout', 'candidate_output_limit', 'candidate_nonzero', 'candidate_oom')),
             'closed_episode_category')
        output_pin = None if token.body is None else pin(token.body)
        binding = decode(token.binding_bytes, CAP)
        need(binding == {'shared': expected_binding, 'arm': arm, 'mode': ARMS[arm],
                         'program': expected_binding['programs'][arm], 'submission': output_pin,
                         'status': token.status, 'failure_reason': token.failure_reason},
             'exact_pair_task_input_program_budget_mode_output_binding')
        if token.status == 'completed':
            try:
                scorer.validate(scorer.decode(token.body))
            except scorer.InvalidSubmission:
                invalid[arm] = True
        commitments.append({'arm': arm, 'commitment': pin(token.binding_bytes),
                            'submission': output_pin, 'status': token.status,
                            'failure_reason': token.failure_reason, 'lifecycle': decode(token.lifecycle_pin_bytes)})
    root = plain(root); root.mkdir(mode=0o700)
    write(root / 'BOTH_CLOSED.private.json', encode({'schema': 'tms_fixed_regions_both_closed_v1',
          'commitments': commitments, 'shared_binding': pin(encode(expected_binding))}), budget)
    expected = entry_pin(reference_selection, CAP)
    # The private reference has not been opened anywhere above this line.
    reference = read(reference_selection['path'], expected, budget, cap=CAP)
    scorer.submission_from_reference(scorer.decode(reference, scorer.InvalidReference))
    reports = {}
    for token in closed:
        if token.status == 'execution_failed':
            report = {'status': 'execution_failed', 'reason': token.failure_reason,
                      'score': 0.0, 'reference_values_exposed': False}
        elif token.arm in invalid:
            report = {'status': 'invalid_submission', 'score': 0.0, 'reference_values_exposed': False}
        else:
            report = {'status': 'scored', 'result': scorer.score_submission(
                token.body, reference, expected['sha256'])}
        write(root / (token.arm + '.SCORE.private.json'), encode(report), budget)
        reports[token.arm] = report
    return {'schema': 'tms_fixed_regions_pair_assessment_v1', 'arms': reports,
            'all_candidates_closed_before_reference': True, 'feedback_to_candidates': False}


def execute_pair(selection, documents, *, root, scorer, reference_selection, budget, active_deadline,
                 cli_configuration):
    """Root-only entry point; requires separately adopted runtime/source evidence.

    A fresh owner process and its already-reviewed outer watchdog must call this
    function. It does not install a second watchdog or invent model-call budgets.
    """
    selection_pin = validate_selection(selection, documents)
    need(entry_pin(reference_selection, CAP) == PROTECTED_REFERENCE, 'exact_protected_reference_selection')
    need(time.monotonic() + 300 < active_deadline < budget.deadline - 30, 'two_full_arm_windows_and_cleanup')
    root = plain(root); need(',' not in str(root), 'literal_mount_source'); root.mkdir(mode=0o700)
    binding = shared_binding(selection, documents)
    write(root / 'OWNER_SELECTION.private.json', encode({'selection': selection, 'pin': selection_pin}), budget)
    input_packet = stage_inputs(root / 'input', selection['input_files'], budget)
    tasks = {a: stage_task(root / ('task-' + a), a, documents, selection['paper'],
                          selection['official_code'], budget) for a in ARMS}
    need(tasks['A']['shared'] == tasks['B']['shared'] and not tasks['A']['code'] and
         tasks['B']['code'] == binding['official_code'], 'only_reviewed_official_code_differs')
    programs = root / 'programs'; programs.mkdir(mode=0o700)
    for arm, entry in selection['programs'].items():
        body = read(entry['path'], entry_pin(entry, 262144), budget, cap=262144)
        need(b'\0' not in body, 'frozen_text_program'); body.decode('utf-8')
        write(programs / (arm + '.py'), body, budget)
    os.chmod(programs, 0o500)
    delivered = [Path(input_packet['path']), *(Path(tasks[a]['path']) for a in ARMS), programs]
    censuses = [sealed_census(path) for path in delivered]
    # Stream reservation (two streams/arm), immutable copies, journals, metadata
    # and failure evidence must fit before any Docker client is dispatched.
    need(budget.write_limit - budget.reserved >= 32 * MIB and
         budget.read_limit - budget.reads >= 32 * MIB, 'pair_failure_retention_allowance')
    docker_owner.require_configured_cli(cli_configuration, budget)
    closed = []
    for arm in ARMS:
        need([sealed_census(path) for path in delivered] == censuses, 'unchanged_delivered_files_before')
        need(time.monotonic() + 120 < active_deadline, 'equal_full_candidate_window')
        run = docker_owner.run_candidate(root=root / ('run-' + arm), input_dir=Path(input_packet['path']),
            task_dir=Path(tasks[arm]['path']), program=programs / (arm + '.py'),
            budget=budget, active_deadline=time.monotonic() + 120)
        need([sealed_census(path) for path in delivered] == censuses, 'unchanged_delivered_files_after')
        closed.append(_freeze(run, arm, binding, budget))
    return closed_pair_score(tuple(closed), binding, reference_selection, scorer=scorer,
                             root=root / 'assessment', budget=budget)
