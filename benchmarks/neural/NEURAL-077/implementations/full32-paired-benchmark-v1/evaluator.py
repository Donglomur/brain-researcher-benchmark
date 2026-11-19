"""Offline full32 paired evaluator and authenticated single-query projection.

This module does not execute participants or enforce a sandbox. An external
trusted capture producer must supply complete immutable arms, including every
first response and owned-closure record required by _admit_public_arm. Hashes and
records do not establish provider isolation or truthful capture on their own.
Both public arms pass admission before any private labels are opened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
import time
import types

HERE = Path(__file__).resolve().parent
CONDITIONS = ('numeric_direct_four_demo', 'numeric_program_four_demo')
PEOPLE = ['sub-008', 'sub-009'] + [f'sub-{i:03d}' for i in range(11, 41)]
COUNT = 6400
PREFIX = struct.Struct('!I')
PROMPT_CAP = 196608
RESPONSE_CAP = 4096
ARM_OUTPUT_CAP = 2 * 1024**3
EVALUATOR_READ_CAP = 8 * 1024**3
POLICY = {
    'same_four_demonstrations': True, 'single_query_only': True,
    'no_other_query_or_pooled_learning': True, 'no_private_answers': True,
    'no_six_person_training_or_fitted_coefficients': True,
    'no_natural_class_prior': True, 'both_bundles_frozen_before_query_access': True,
    'old_negative_baselines_preserved': True, 'no_feedback_until_pair_closed': True,
}



def need(ok, message):
    if not ok:
        raise ValueError(message)



def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()



def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}



def decode(body):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON field')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))



def descriptor(value, cap):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
         type(value['bytes']) is int and 0 < value['bytes'] <= cap and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'Exact bounded descriptor required')



def ordinary_path(path):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'Symlink path refused')
    return path



def read(path, cap, expected=None, budget=None, empty=False):
    path = ordinary_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             (0 if empty else 1) <= before.st_size <= cap, 'Bounded ordinary input required')
        if budget is not None:
            need(budget['read'] + before.st_size <= EVALUATOR_READ_CAP, 'Evaluator read cap')
            budget['read'] += before.st_size
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    need(len(body) == before.st_size and fields(before) == fields(after) == fields(path.lstat()),
         'Input changed during capture')
    need(expected is None or pin(body) == expected, 'Input commitment mismatch')
    return body



def write(path, body, budget=None):
    if budget is not None:
        need(budget['written'] + len(body) <= ARM_OUTPUT_CAP, 'Arm output cap')
        budget['written'] += len(body)
    path = ordinary_path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    return pin(body)



def load_source(name, path, body):
    module = types.ModuleType(name); module.__file__ = str(path); sys.modules[name] = module
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module



def dependencies():
    """Load only two adjacent, fully pinned trusted-source modules."""
    body = read(HERE / 'SOURCE_BINDINGS.json', 16384)
    bindings = decode(body)
    need(set(bindings) == {'schema', 'members'} and
         bindings['schema'] == 'erp-full32-portable-evaluator-sources-v1', 'Portable evaluator source bindings required')
    need(set(bindings['members']) == {'bundle', 'consumer'}, 'Exact offline source closure')
    modules = {}
    for name, row in bindings['members'].items():
        need(set(row) == {'path', 'bytes', 'sha256'} and row['path'] == name + '.py',
             'Only exact adjacent trusted-source members')
        expected = {key: row[key] for key in ('bytes', 'sha256')}
        captured = read(HERE / row['path'], 65536, expected)
        modules[name] = load_source('erp_full32_portable_' + name, HERE / row['path'], captured)
    return modules, pin(body)



def validate_contract(contract):
    need(type(contract) is dict and set(contract) == {
        'schema', 'selected', 'condition_id', 'public_root', 'public_manifest',
        'source_bindings', 'operator_source', 'bundles', 'interpreter', 'limits', 'information_policy',
        'authoring_exposure_declaration', 'direct_provider_qualification'}, 'Exact pair contract fields')
    need(contract['schema'] == 'erp-full6400-selected-pair-v1' and contract['selected'] is True,
         'Separate selected pair contract required')
    need(contract['condition_id'] == 'erp-core-remaining-persons-released-marker-v1', 'Condition identity')
    need(contract['information_policy'] == POLICY, 'Matched information and prospective freeze required')
    need(type(contract['authoring_exposure_declaration']) is str and
         1 <= len(contract['authoring_exposure_declaration']) <= 8192, 'Explicit authoring exposure declaration')
    need(contract['direct_provider_qualification'] == 'unqualified_local_driver',
         'This local runner does not qualify a no-tools provider')
    need(type(contract['public_root']) is str and Path(contract['public_root']).is_absolute(), 'Absolute operator public root')
    descriptor(contract['public_manifest'], 131072); descriptor(contract['source_bindings'], 16384)
    descriptor(contract['operator_source'], 65536)
    need(type(contract['bundles']) is dict and set(contract['bundles']) == set(CONDITIONS),
         'Both full bundles must be committed before either arm')
    for row in contract['bundles'].values():
        need(type(row) is dict and set(row) == {'path', 'file', 'bundle_identity'}, 'Exact frozen participant descriptor')
        need(type(row['path']) is str and Path(row['path']).is_absolute(), 'Absolute frozen participant path')
        descriptor(row['file'], 1048576); descriptor(row['bundle_identity'], 1048576)
    interpreter = contract['interpreter']
    need(type(interpreter) is dict and set(interpreter) == {'path', 'file'}, 'Exact interpreter declaration')
    descriptor(interpreter['file'], 64 * 1024**2)
    need(type(interpreter['path']) is str and Path(interpreter['path']).is_absolute(), 'Absolute interpreter')
    limits = contract['limits']
    need(type(limits) is dict and set(limits) == {'episode_work_seconds', 'episode_cleanup_seconds', 'campaign_seconds'},
         'Exact episode/campaign budgets')
    need(all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in limits.values()), 'Positive finite clocks')
    need(limits['episode_work_seconds'] <= 3600 and limits['episode_cleanup_seconds'] <= 30 and
         limits['campaign_seconds'] <= 2**31, 'Declared finite execution limits')
    return contract



def verify_operator(contract):
    """The selected contract pins this offline evaluator as well as its dependencies."""
    return pin(read(HERE / 'evaluator.py', 65536, contract['operator_source']))



def freeze(root, manifest, output):
    modules, _ = dependencies()
    frozen = modules['bundle'].capture(root, decode(read(manifest, 65536)))
    write(output, modules['bundle'].encoded(frozen))
    return {'status': 'bundle_frozen_before_prompts', 'file': pin(read(output, 1048576)),
            'bundle_identity': frozen['bundle_identity'], 'private_target_reads': 0}



def context_frame(context, condition):
    need(type(context) is dict and set(context) == {'trial_id', 'condition', 'prompt', 'context_sha256'},
         'Only one complete participant context')
    need(context['condition'] == condition and re.fullmatch('q-[0-9a-f]{32}', context['trial_id']) and
         type(context['prompt']) is str, 'Opaque query identity and condition')
    body = context['prompt'].encode('utf-8')
    need(0 < len(body) <= PROMPT_CAP and pin(body)['sha256'] == context['context_sha256'],
         'Complete context exceeds capacity or changed; no truncation')
    return PREFIX.pack(len(body)) + body



def load_contract(path, expected):
    body = read(path, 65536, expected)
    return validate_contract(decode(body)), pin(body)



def parse_prediction_rows(body, ids):
    expected = set(ids); need(len(expected) == len(ids), 'Duplicate expected identity')
    values = {}
    for line in body.splitlines(keepends=True):
        need(line.endswith(b'\n') and len(line) <= 4096, 'Bounded complete prediction line')
        row = decode(line)
        need(type(row) is dict and set(row) == {'trial_id', 'target_probability'}, 'Exact prediction fields')
        identifier, probability = row['trial_id'], row['target_probability']
        need(type(identifier) is str and identifier in expected and identifier not in values,
             'Unknown or duplicate prediction identity')
        need(type(probability) in (int, float) and math.isfinite(probability) and 0 <= probability <= 1,
             'Finite nonboolean probability required')
        values[identifier] = float(probability)
    need(set(values) == expected, 'Every expected prediction required')
    return values



def _admit_public_arm(desc, condition, contract, contract_pin, session, modules, budget, deadline):
    need(set(desc) == {'root', 'receipt'}, 'Exact public arm descriptor')
    root = ordinary_path(desc['root']); body = read(root / 'ARM.json', 4 * 1024**2, desc['receipt'], budget)
    receipt = decode(body)
    need(receipt['schema'] == 'erp-full6400-numeric-arm-v1' and receipt['status'] == 'closed_unscored_arm' and
         receipt['condition'] == condition and receipt['contract'] == contract_pin and
         receipt['source_bindings'] == contract['source_bindings'] and receipt['public_manifest'] == contract['public_manifest'] and
         receipt['bundle_identity'] == contract['bundles'][condition]['bundle_identity'] and
         receipt['query_count'] == COUNT and receipt['attempt_inventory_count'] == COUNT and
         receipt['private_target_reads'] == 0 and receipt['scoring_performed'] is False, 'Complete selected closed arm required')
    retained_frozen = read(root / 'FROZEN.json', 1048576, contract['bundles'][condition]['file'], budget)
    frozen = decode(retained_frozen)
    client = modules['bundle'].verify(frozen)  # Validate/compile declarations, never import/execute candidate code.
    need(frozen['bundle_identity'] == contract['bundles'][condition]['bundle_identity'], 'Retained frozen participant changed')
    read(root / 'CLIENT.py', 1048576, pin(client), budget)
    predictions_body = read(root / 'collection/predictions.jsonl', 2 * 1024**2, receipt['predictions'], budget)
    predictions = parse_prediction_rows(predictions_body, session.trial_ids)
    collection = decode(read(root / 'collection/COMPLETE.json', 131072, receipt['collection'], budget))
    need(collection['status'] == 'complete_unscored_submission' and collection['condition'] == condition and
         collection['responses'] == COUNT and collection['predictions'] == receipt['predictions'] and
         collection['manifest_pin'] == contract['public_manifest'], 'Complete target-blind collection required')
    need(len(receipt['episodes']) == COUNT, 'Every episode closure required')
    for ordinal, (identifier, episode_pin) in enumerate(zip(session.trial_ids, receipt['episodes'], strict=True)):
        need(time.monotonic() < deadline, 'Protected evaluator deadline')
        need(episode_pin['trial_id'] == identifier and episode_pin['status'] == 'ok', 'Failed or mixed episode')
        path = root / f'{ordinal:04d}'
        end = decode(read(path / 'END.json', 16384, episode_pin['end'], budget))
        cleanup = end['owned_cleanup']
        need(end['schema'] == 'erp-full6400-owned-episode-v1' and end['status'] == 'ok' and
             end['trial_id'] == identifier and end['condition'] == condition and end['returncode'] == 0 and
             type(end['pid']) is int and end['pid'] > 1 and cleanup['pid'] == end['pid'] and
             cleanup['cleanup_complete'] is True and cleanup['reaped'] is True and cleanup['group_absence_observed'] is True and
             end['stdout_EOF_observed'] is True and end['normal_exit_observed'] is True and
             end['generated_protocol_only'] is False, 'Unclosed or generated episode cannot enter protected grading')
        context = session.context(identifier, condition)
        incoming = read(path / 'INPUT.bin', PROMPT_CAP + 4, end['input'], budget)
        need(incoming == context_frame(context, condition) and end['context_sha256'] == context['context_sha256'],
             'Delivered full context differs from matched packet')
        outgoing = read(path / 'OUTPUT.bin', RESPONSE_CAP + 4, end['output'], budget)
        need(len(outgoing) > 4 and PREFIX.unpack(outgoing[:4])[0] == len(outgoing) - 4, 'Single complete response frame')
        need(modules['consumer'].parse_response(outgoing[4:].decode('utf-8'), identifier) == predictions[identifier],
             'Prediction differs from immutable first frame')
    return predictions



def load_private_people(descriptor_value, public_manifest, ids, budget):
    """Called only after both public arms and every closure have passed."""
    need(set(descriptor_value) == {'root', 'complete'}, 'Exact private material descriptor')
    root = ordinary_path(descriptor_value['root'])
    complete = decode(read(root / 'COMPLETE.json', 4 * 1024**2, descriptor_value['complete'], budget))
    need(complete['schema'] == 'erp-core-full32-packet-census-v1' and
         complete['status'] == 'full32_packet_materialized_no_models' and complete['full_cohort_complete'] is True and
         complete['query_count'] == COUNT and complete['files']['public/PACKET.json'] == public_manifest and
         complete['uncommitted_files'] == [] and len(complete['participants']) == 32 and
         [r['participant_id'] for r in complete['participants']] == PEOPLE and
         all(r['status'] == 'packet_person_complete' for r in complete['participants']),
         'Full32 private/public material commitment')
    joins = decode(read(root / 'private/PARTICIPANT_JOIN.json', 262144,
                        complete['files']['private/PARTICIPANT_JOIN.json'], budget))
    need(type(joins) is list and [r['participant_id'] for r in joins] == PEOPLE, 'Exact full32 private roster')
    people = {}; seen = set()
    for join in joins:
        need(set(join) == {'participant_id', 'opaque_person_id', 'trials', 'record', 'path'} and
             join['trials'] == 200 and re.fullmatch('p-[0-9a-f]{24}', join['opaque_person_id']) and
             join['path'] == 'private/people/' + join['opaque_person_id'] + '.json', 'Exact private person join')
        need(complete['files'][join['path']] == join['record'], 'Private person commitment differs')
        person = decode(read(root / join['path'], 262144, join['record'], budget))
        need(person['participant_id'] == join['participant_id'] and person['opaque_person_id'] == join['opaque_person_id'] and
             len(person['trials']) == 200, 'Exact private person record')
        rows = []
        for row in person['trials']:
            identifier, label = row['trial_id'], row['target']
            need(identifier in ids and identifier not in seen and type(label) is int and label in (0, 1),
                 'Private labels must join unique public opaque identities')
            seen.add(identifier); rows.append((identifier, label))
        need(sum(label for _, label in rows) == 40, 'Authenticated40/160 per-person class support')
        people[join['participant_id']] = rows
    need(seen == set(ids), 'Every public query must join one private person')
    return people



def metric_rows(predictions, private_people):
    """Equal-person metrics; pure generated controls are not scientific outcomes."""
    rows = []
    for person, trials in private_people.items():
        need(trials and all(type(y) is int and y in (0, 1) for _, y in trials), 'Binary class labels')
        targets = sum(y for _, y in trials); standards = len(trials) - targets
        need(targets > 0 and standards > 0, 'Both classes required for each person')
        true_positive = true_negative = 0; loss = 0.0
        for identifier, label in trials:
            probability = predictions[identifier]
            need(type(probability) in (int, float) and math.isfinite(probability) and 0 <= probability <= 1,
                 'Finite prediction required')
            true_positive += int(label == 1 and probability >= .5)
            true_negative += int(label == 0 and probability < .5)
            clipped = min(1 - 1e-15, max(1e-15, probability))
            loss -= math.log(clipped if label else 1 - clipped)
        rows.append({'participant_id': person, 'trials': len(trials), 'targets': targets, 'standards': standards,
                     'target_true_positive': true_positive, 'standard_true_negative': true_negative,
                     'balanced_accuracy': .5 * (true_positive / targets + true_negative / standards),
                     'natural_log_loss': loss / len(trials)})
    need(rows, 'Nonempty participant panel')
    return {'participants': rows,
            'participant_macro_balanced_accuracy': sum(r['balanced_accuracy'] for r in rows) / len(rows),
            'participant_macro_natural_log_loss': sum(r['natural_log_loss'] for r in rows) / len(rows)}



def protected_evaluate(contract, arm_a_descriptor, arm_b_descriptor, private_material_descriptor, output, *,
                       contract_pin, deadline, session_factory=None, modules=None):
    """Private descriptor is not interpreted until both complete public arms pass."""
    validate_contract(contract)
    verify_operator(contract)
    # PacketSession authenticates each <=384MB query store and the two public
    # arm audits read each query once more. Reserve those internal reads plus
    # source/metadata overhead before its first call; our own reads add exactly.
    budget = {'read': 3 * 384000000 + 16 * 1024**2}
    if modules is None:
        modules, source_identity = dependencies(); need(source_identity == contract['source_bindings'], 'Source bindings changed')
    factory = session_factory or modules['consumer'].PacketSession
    with factory(contract['public_root'], contract['public_manifest']) as session:
        need(len(session.trial_ids) == COUNT and len(set(session.trial_ids)) == COUNT, 'Full6400 public roster')
        a = _admit_public_arm(arm_a_descriptor, CONDITIONS[0], contract, contract_pin, session, modules, budget, deadline)
        b = _admit_public_arm(arm_b_descriptor, CONDITIONS[1], contract, contract_pin, session, modules, budget, deadline)
        # No candidate module is ever imported by the evaluator. Only now can
        # the operator-supplied private pathname and target bytes be interpreted.
        people = load_private_people(private_material_descriptor, contract['public_manifest'], set(session.trial_ids), budget)
    scores = {CONDITIONS[0]: metric_rows(a, people), CONDITIONS[1]: metric_rows(b, people)}
    differences = [{'participant_id': x['participant_id'],
                    'direct_minus_program_balanced_accuracy': x['balanced_accuracy'] - y['balanced_accuracy'],
                    'direct_minus_program_natural_log_loss': x['natural_log_loss'] - y['natural_log_loss']}
                   for x, y in zip(scores[CONDITIONS[0]]['participants'], scores[CONDITIONS[1]]['participants'], strict=True)]
    result = {'schema': 'erp-full32-protected-pair-evaluation-v1', 'status': 'complete_finite_cohort_pair',
              'people': 32, 'queries': COUNT, 'scores': scores, 'paired_person_differences': differences,
              'primary_direct_minus_program_macro_BA': sum(x['direct_minus_program_balanced_accuracy'] for x in differences) / 32,
              'both_public_arms_and_owned_closures_validated_before_private': True,
              'contract': contract_pin, 'public_arm_receipts': [arm_a_descriptor['receipt'], arm_b_descriptor['receipt']],
              'read_bytes_charged': budget['read'],
              'read_charge_scope': 'Conservative: fixed1,168,777,216-byte PacketSession/source overhead reservation plus explicit captured file sizes; not measured physical I/O.',
              'outer_campaign_and_resource_qualification_required': True, 'new_benchmarks': 0,
              'provider_context_qualified': False, 'provider_tool_policy_qualified': False,
              'interpretation': 'Event-label classification for this finite public cohort; no physiological P3-presence or pretrained-source-unseen claim. Local driver scores alone are not a qualified direct-model comparison.',
              'bootstrap_interval': 'Not computed by this core scorer. The separately frozen protocol requires the secondary10000 paired-person PCG64 bootstrap before reporting that interval.'}
    need(time.monotonic() < deadline, 'Evaluator deadline before final output')
    output = ordinary_path(output); output.mkdir(mode=0o700)
    write(output / 'RESULT.json', encode(result))
    return result



def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    freeze_parser = sub.add_parser('freeze', help='Capture declared source/config before any query')
    for name in ('root', 'manifest', 'output'):
        freeze_parser.add_argument('--' + name, type=Path, required=True)
    project = sub.add_parser('project', help='Emit exactly one authenticated four-demo context')
    project.add_argument('--public-root', type=Path, required=True)
    project.add_argument('--manifest-bytes', type=int, required=True)
    project.add_argument('--manifest-sha256', required=True)
    project.add_argument('--trial-id', required=True)
    project.add_argument('--condition', choices=CONDITIONS, required=True)
    grade = sub.add_parser('evaluate', help='Audit both externally captured arms before opening labels')
    for name in ('contract', 'public-arms', 'private-material', 'output'):
        grade.add_argument('--' + name, type=Path, required=True)
    grade.add_argument('--contract-bytes', type=int, required=True)
    grade.add_argument('--contract-sha256', required=True)
    grade.add_argument('--work-seconds', type=float, required=True)
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        result = freeze(args.root, args.manifest, args.output)
    elif args.command == 'project':
        modules, _ = dependencies()
        identity = {'bytes': args.manifest_bytes, 'sha256': args.manifest_sha256}
        with modules['consumer'].PacketSession(args.public_root, identity) as session:
            result = session.context(args.trial_id, args.condition)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    else:
        started = time.monotonic()
        need(math.isfinite(args.work_seconds) and args.work_seconds > 0, 'Finite positive evaluation clock')
        identity = {'bytes': args.contract_bytes, 'sha256': args.contract_sha256}
        descriptor(identity, 65536)
        contract, _ = load_contract(args.contract, identity)
        arms = decode(read(args.public_arms, 65536))
        need(set(arms) == set(CONDITIONS), 'Both public arm descriptors')
        # Even the private descriptor file is not opened until both arms pass.
        private_path = args.private_material
        class LazyPrivate(dict):
            def materialize(self):
                self.update(decode(read(private_path, 65536)))
                return self
        lazy = LazyPrivate()
        original = globals()['load_private_people']
        def later(value, *rest):
            return original(value.materialize(), *rest)
        globals()['load_private_people'] = later
        try:
            result = protected_evaluate(contract, arms[CONDITIONS[0]], arms[CONDITIONS[1]], lazy, args.output,
                                        contract_pin=identity, deadline=started + args.work_seconds)
        finally:
            globals()['load_private_people'] = original
    print(json.dumps({'status': result['status'], 'new_benchmarks': 0}, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
