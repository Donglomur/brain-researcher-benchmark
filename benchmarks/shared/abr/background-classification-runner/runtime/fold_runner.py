"""ABR-specific staging and ten-episode composition of the accepted Docker owner.

This is evaluator code. Nothing in this module enters a candidate mount. The
container lifecycle remains the reused create/inspect/start/remove implementation.
No arbitrary executable backend or candidate Python import exists in this path.
"""
import hashlib
import os
from pathlib import Path
import stat
import time

import builder
import common as c
import docker_owner
import fold_context
import packet
import prepared_manifest
import split

ROUTES = ('candidate', 'layout_only')
DOCS = ('TASK.md', 'SUBMISSION_SCHEMA.json')
PROFILE = {'animals': 104, 'records': 16226, 'samples': 31689378, 'stacks': 936}
MIB = 1024 * 1024


def entry_pin(entry, cap):
    c.need(type(entry) is dict and set(entry) == {'path', 'bytes', 'sha256'}, 'closed selected locator')
    c.plain(entry['path'])
    return c.admit_pin({k: entry[k] for k in ('bytes', 'sha256')}, cap)


class PacketBudget:
    """Adapt the unchanged packet loader's single read meter to owner accounting."""
    def __init__(self, budget): self.budget = budget
    def charge(self, kind, amount):
        c.need(kind == 'read', 'packet loader reads only')
        self.budget.charge_read(amount)
    def check(self): self.budget.check()


def census(root):
    root = c.plain(root); result = {}
    for path in (root, *sorted(root.rglob('*'))):
        s = path.lstat()
        if stat.S_ISDIR(s.st_mode):
            c.need(stat.S_IMODE(s.st_mode) == 0o500, 'sealed fold directory')
        else:
            c.need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and
                   stat.S_IMODE(s.st_mode) == 0o400, 'sealed single-link fold file')
        result[str(path)] = c.signature(s)
    return result


def stage_fold(root, manifest, fold, route, load_animal, budget):
    """Only the current fold's public header and 104 complete raw/layout objects."""
    root = c.plain(root); root.mkdir(mode=0o700)
    animals = root / 'animals'; animals.mkdir(mode=0o700)
    header = fold_context.public_header(manifest, fold, route)
    c.write(root / 'FOLD.json', packet.canonical(header) + b'\n', budget)
    counts = dict.fromkeys(PROFILE, 0); pins = []
    for item in fold_context.iter_animals(manifest, fold, route, load_animal):
        budget.check(); value = item['animal']; records = value['records']
        counts['animals'] += 1; counts['records'] += len(records)
        counts['samples'] += sum(len(row['sample_indices']) for row in records)
        counts['stacks'] += len({row['stimulus'] for row in records})
        # The inherited projector validates strict source keys, then removes
        # every sample value for the layout route. No waveform hash is exported.
        c.need((value['schema'] == 'abr-background-layout/v1') == (route == 'layout_only'),
               'route-specific input schema')
        if route == 'layout_only':
            c.need(all('samples' not in row for row in records), 'layout without waveform')
        raw = packet.canonical(value) + b'\n'
        c.need(len(raw) <= 16*MIB, 'one complete admitted animal extent')
        pins.append(c.write(animals / (value['animal_id'] + '.json'), raw, budget))
    c.need(counts == PROFILE, 'complete original cohort records samples and stacks')
    os.chmod(animals, 0o500); os.chmod(root, 0o500)
    return {'header': c.pin(packet.canonical(header) + b'\n'), 'counts': counts,
            'animals': pins, 'sealed': census(root)}


def freeze_closed(episode, root, budget):
    """Accept only the owner-created capability after authenticated cleanup."""
    docker_owner.require_closed_episode(episode)
    life = c.decode(c.read(episode.lifecycle['path'], entry_pin(episode.lifecycle, MIB),
                           budget, cap=MIB, mode=0o400), MIB)
    c.need(life['episode_closed'] is True and life['remaining_owned_cid'] is None and
           not life['publication_errors'] and not life['journal']['persistence_errors'] and
           life['journal']['closed'] is True, 'closed complete evidence before predictions')
    if type(episode) is docker_owner.ClosedFailure:
        c.need(life['candidate_closed'] is False and life['submission'] is None and
               life['failed_episode_reason'] == episode.reason, 'owned candidate failure join')
        c.write(root/'CLOSED_CANDIDATE_FAILURE.private.json', c.encode({
            'reason': episode.reason, 'lifecycle': episode.lifecycle,
            'metric': None, 'all104_predictions_available': False}), budget)
        raise c.Refusal('closed candidate failure; complete campaign has no score')
    c.need(life['candidate_closed'] is True and life['failure'] is None and
           life['submission'] == episode.submission, 'natural candidate lifecycle join')
    raw = c.read(episode.submission['path'], entry_pin(episode.submission, 2*MIB),
                 budget, cap=2*MIB, mode=0o400)
    # Strict decoding precedes the unchanged complete-fold validator. Candidate
    # bytes are data; they are never imported, eval'ed, unpickled or executed here.
    rows = c.decode(raw, 2*MIB)
    return rows, c.pin(c.encode(life)), c.pin(raw)


def execute(selection, documents, *, root, budget, active_deadline):
    """One immutable program pair, ten fresh contexts, one final private score.

    Runtime/source/capacity admission belongs to runner_config before this call.
    The same accepted Docker owner/configuration is used for both routes.
    """
    c.need(selection['root_execution_selected'] is True, 'root selected complete campaign')
    c.need(set(documents) == set(DOCS), 'exact participant instructions')
    c.need(time.monotonic() + 6600 < active_deadline < budget.deadline,
           'complete ten-fold work and cleanup windows')
    root = c.plain(root); root.mkdir(mode=0o700)
    frozen = root/'frozen-methods'; frozen.mkdir(mode=0o700)
    method_pins = {}
    # These are operator-selected bytes frozen before opening any packet or
    # manifest. No output, trained state, log, or conversation becomes a method.
    c.need(set(selection['programs']) == set(ROUTES), 'both frozen methods')
    for route in ROUTES:
        e = selection['programs'][route]
        raw = c.read(e['path'], entry_pin(e, 262144), budget, cap=262144)
        c.need(b'\0' not in raw, 'text prediction program'); raw.decode('utf8')
        method_pins[route] = c.write(frozen/(route+'.py'), raw, budget)
    os.chmod(frozen, 0o500)
    task = root/'task'; task.mkdir(mode=0o700)
    for name, raw in documents.items():
        c.need(type(raw) is bytes and 0 < len(raw) <= 65536, 'bounded task document')
        c.write(task/name, raw, budget)
    os.chmod(task, 0o500)
    shared_census = (census(task), census(frozen))
    packet_root = c.plain(selection['packet_root'])
    completion_entry = selection['completion']
    c.need(completion_entry['path'] == str(packet_root/'evaluator/PACKET_COMPLETION.json'),
           'exact private completion location')
    comp_raw = c.read(completion_entry['path'], entry_pin(completion_entry, MIB), budget, cap=MIB)
    completion = builder.decode(comp_raw)
    c.need(completion['schema'] == 'abr-background-opaque-packet-completion/v1' and
           completion['profile'] == packet.PROFILE and completion['sample_count'] == PROFILE['samples'],
           'complete trusted packet metadata')
    me = selection['manifest']
    c.need(me['path'] == str(packet_root/'evaluator/PRIVATE_MANIFEST.json'), 'fixed manifest location')
    raw = c.read(me['path'], entry_pin(me, MIB), budget, cap=MIB)
    prepared_manifest.admit(selection, raw, comp_raw, budget)
    manifest = split.validate_manifest(builder.decode(raw))
    c.write(root/'PREPARATION_BOUNDARY.private.json', c.encode({
        'preparation':selection['preparation'], 'manifest':selection['manifest'],
        'completion':selection['completion'], 'before_any_actor':True}), budget)
    c.need(split.digest(manifest) == completion['private_manifest_sha256'], 'packet/private manifest join')
    loader = fold_context.pinned_animal_loader(packet_root, completion_entry, PacketBudget(budget))
    campaign = fold_context.Campaign(manifest, method_pins['candidate']['sha256'],
                                      method_pins['layout_only']['sha256'])
    cli = docker_owner.configure_cli(root/'private-cli-config', budget)
    c.write(root/'CLI.private.json', c.encode(cli), budget)
    committed = []
    # Order is fixed before data: route then fold. A fresh container has private
    # /work and /tmp each time; no other fold, label ledger or evaluator is mounted.
    for route in ROUTES:
        for fold in range(5):
            budget.check()
            c.need(time.monotonic()+660 < active_deadline, 'full current fold allowance')
            episode_root = root/(route+'-'+str(fold)); episode_root.mkdir(mode=0o700)
            context_id = hashlib.sha256(str(episode_root).encode()).hexdigest()
            campaign.start(route, fold, context_id)
            staged = stage_fold(episode_root/'input', manifest, fold, route, loader, budget)
            c.write(episode_root/'INPUT_COMMITMENT.private.json', c.encode({
                k: v for k,v in staged.items() if k != 'sealed'}), budget)
            docker_owner.require_configured_cli(cli, budget)
            episode = docker_owner.run_candidate(root=episode_root/'execution',
                input_dir=episode_root/'input', task_dir=task,
                program=Path(method_pins[route]['path']), budget=budget,
                active_deadline=min(active_deadline, time.monotonic()+660))
            c.need(not docker_owner.registered_clients(), 'all fold Docker clients closed')
            c.need(census(episode_root/'input') == staged['sealed'] and
                   (census(task), census(frozen)) == shared_census, 'input and method immutability')
            rows, life_pin, raw_pin = freeze_closed(episode, episode_root, budget)
            # This returns only a commitment, never accuracy/correctness/labels.
            commit = campaign.commit_stopped(context_id, rows, life_pin['sha256'])
            record = {'route': route, 'outer_fold': fold, 'context_id': context_id,
                'program': method_pins[route], 'lifecycle': episode.lifecycle,
                'raw_submission': raw_pin, 'commitment': commit}
            c.write(episode_root/'COMMIT.private.json', c.encode(record), budget)
            committed.append(record)
    c.need(len(committed) == 10 and not docker_owner.registered_clients(), 'complete ten closed folds')
    barrier = c.write(root/'ALL_104_PAIRED_COMMITTED.private.json', c.encode({
        'candidate_predictions':104, 'layout_predictions':104, 'folds':committed,
        'feedback_issued':False}), budget)
    # Sole scoring call. Its complete private labels never enter a participant
    # namespace, and no subsequent actor is dispatched after this feedback.
    result = campaign.evaluate()
    result['external_owner'] = {'ten_fresh_closed_containers': True,
        'barrier': barrier, 'runtime_identity': docker_owner.IMAGE,
        'native_runtime_validation_performed_by_this_source_run': False}
    report = c.write(root/'EVALUATION.private.json', c.encode(result), budget)
    return {'schema':'abr-protected-complete-campaign/v1', 'report':report,
        'paired_complete_predictions':208, 'containers':10, 'new_benchmark_ids':0,
        'scientific_qualification':False, 'candidate_feedback_during_work':False}
