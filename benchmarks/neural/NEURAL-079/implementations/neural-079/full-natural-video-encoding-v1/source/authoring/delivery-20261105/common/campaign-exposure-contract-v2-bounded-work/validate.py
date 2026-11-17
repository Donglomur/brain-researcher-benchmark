"""Validate explicit campaign exposure claims; never launch or select a task."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

HERE = Path(__file__).absolute().parent
POLICY = {"schema":"campaign_bounded_admission_policy_v2","work_body_bytes":2097152,"aggregate_bytes":4194304,"construction_margin_bytes":262144,"construction_work_max_bytes":1835008,"request_bytes":131072,"preference_bytes":262144,"source_bytes":262144,"wrapper_bytes":262144,"registration_bytes":131072,"manifest_bytes":32768,"source_member_bytes":200000,"validator_bytes":20000,"audit_bytes":250000,"builder_bytes":20000,"declaration_descriptor_bytes":100000,"declaration_bytes":10000,"report_bytes":1000000,"finish_bytes":16384,"invocation_bytes":65536,"installer_metadata_bytes":2097152}
KINDS = {'development_only', 'fresh_targets', 'new_animal', 'new_session',
         'new_stimuli', 'independent_acquisition', 'new_paper'}
RELATIONS = {'shared_declared_neural_source', 'shared_literal_overlap_label',
             'shared_exact_paper_locator', 'shared_exact_data_locator',
             'catalog_declared_source_to_paper', 'shared_research_source_family',
             'shared_stimulus_family', 'shared_named_acquisition_family',
             'shared_named_participant'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def parse(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def literal(root, relative):
    need(type(relative) is str, 'literal relative path')
    p = Path(relative)
    need(not p.is_absolute() and '..' not in p.parts and str(p) == relative,
         'canonical relative path')
    path = root / p
    need(not any(x.is_symlink() for x in (path, *path.parents)), 'unlinked path')
    return path


class Reader:
    """Bounded metadata capture only; no descriptor-listed payload is opened."""
    def __init__(self, limit=4194304, *, repo=None, view=None):
        need(type(limit) is int and limit > 0, 'positive reader budget')
        self.limit, self.used, self.repo, self.view = limit, 0, repo, view
        self.receipts = []

    def read(self, path, cap, expected=None):
        path = Path(path).absolute()
        if self.view is not None:
            root = Path(self.repo).absolute()
            need(path.is_relative_to(root), 'view path within repository')
            key = path.relative_to(root).as_posix()
            need(Path(self.view.resolve(root, key)) == path, 'canonical view resolution')
            extent = expected['bytes'] if expected is not None else cap
            need(type(extent) is int and 0 < extent <= cap, 'view extent')
            self.used += extent + 1
            need(self.used <= self.limit, 'metadata read budget')
            raw = self.view.capture(key, cap, expected)
            need(type(raw) is bytes and 0 < len(raw) <= extent, 'bounded view body')
            if expected is not None:
                need(pin(raw) == {k: expected[k] for k in ('bytes','sha256')}, 'view pin')
            self.receipts.append({'path':key, **pin(raw), 'reserved_bytes':extent + 1})
            return raw
        need(not any(x.is_symlink() for x in (path, *path.parents)), 'unlinked input')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                 and 0 < before.st_size <= cap, 'bounded ordinary metadata')
            self.used += before.st_size + 1
            need(self.used <= self.limit, 'metadata read budget')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(before.st_size + 1)
            after = os.fstat(fd)
            named = path.lstat()
            fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
            need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k)
                 == getattr(named, k) for k in fields), 'stable named metadata')
            if expected is not None:
                need(pin(raw) == {k: expected[k] for k in ('bytes', 'sha256')}, 'metadata pin')
            self.receipts.append({'path':str(path), **pin(raw), 'reserved_bytes':before.st_size + 1})
            return raw
        finally:
            os.close(fd)


def known_tasks(audit):
    need(audit['status'] == 'declared_metadata_links_only'
         and audit['candidate_tasks'] == 200, 'exact typed audit schema')
    ids = set(audit['papers_without_detected_cross_suite_edge'])
    ids.update(audit['neural_tasks_without_detected_cross_suite_edge'])
    for row in audit['edges']:
        need(type(row['tasks']) is list and len(row['tasks']) == 2
             and row['tasks'][0] < row['tasks'][1], 'direct canonical edge')
        need(row['relation'] in RELATIONS, 'unknown relationship requires source review')
        ids.update(row['tasks'])
    need(len(ids) == 200 and all(type(x) is str for x in ids), '200 distinct identities')
    return ids


def assess(request, audit, declarations):
    ids = known_tasks(audit)
    need(type(request) is dict and set(request) == {'schema', 'evaluations'}
         and request['schema'] == 'campaign_exposure_request_v1', 'request schema')
    evaluations = request['evaluations']
    need(type(evaluations) is list and 1 <= len(evaluations) <= 200, 'bounded task list')
    need(declarations['schema'] == 'campaign_exposure_declarations_v1', 'declaration schema')
    facts = declarations['tasks']
    need(set(facts) <= ids, 'declared task membership')
    edges = {}
    for row in audit['edges']:
        edges.setdefault(tuple(row['tasks']), set()).add(row['relation'])
    biology = {tuple(sorted(row['tasks'])): row for row in declarations['shared_biology']}
    seen = set()
    decisions = []

    def task_list(value):
        need(type(value) is list and len(value) <= 200 and all(type(x) is str for x in value),
             'explicit task-ID list')
        need(len(value) == len(set(value)) and set(value) <= ids, 'unique known task IDs')
        return set(value)

    for item in evaluations:
        need(type(item) is dict and set(item) == {'task_id', 'prior_access', 'concurrent_inputs', 'claims'},
             'exact evaluation keys')
        task = item['task_id']
        need(type(task) is str and task in ids and task not in seen, 'one record per canonical task')
        seen.add(task)
        prior = task_list(item['prior_access'])
        concurrent = task_list(item['concurrent_inputs'])
        need(task not in concurrent, 'own permitted task inputs are implicit')
        claims = item['claims']
        need(type(claims) is list and 1 <= len(claims) <= len(KINDS), 'explicit bounded claims')
        result = {'task_id': task, 'operational_conflicts': [], 'claims': [],
                  'known_actual_target_exposure': [], 'typed_direct_links': []}
        for exposure in declarations['actual_target_exposure']:
            if exposure['affected_task'] != task:
                continue
            source = exposure['access_task']
            if source in prior | concurrent:
                result['known_actual_target_exposure'].append({
                    'access_task': source, 'affected_task': task,
                    'relation': exposure['relation'],
                    'access': sorted(k for k, values in [('prior', prior), ('concurrent', concurrent)]
                                     if source in values)})
            if source in concurrent and exposure['forbid_concurrent_inputs']:
                result['operational_conflicts'].append({'code': 'forbidden_joint_inputs',
                                                       'access_task': source})
        claim_kinds = set()
        compared = set(prior | concurrent)
        for claim in claims:
            need(type(claim) is dict and set(claim) == {'kind', 'against'}, 'exact claim keys')
            kind = claim['kind']
            need(type(kind) is str and kind in KINDS and kind not in claim_kinds, 'known unique claim')
            claim_kinds.add(kind)
            against = task_list(claim['against'])
            need(task not in against, 'generalization comparison uses distinct task IDs')
            if kind == 'development_only':
                need(not against and len(claims) == 1, 'development-only makes no additional freshness claim')
                status, reasons = 'compatible_development_only', []
            else:
                if kind == 'fresh_targets':
                    need(not against, 'freshness uses declared access, not mere comparisons')
                else:
                    need(bool(against), 'generalization requires explicit comparison tasks')
                compared.update(against)
                relevant = prior | concurrent
                reasons = []
                if kind == 'fresh_targets':
                    if facts.get(task, {}).get('exposed_development') is True:
                        reasons.append({'code': 'declared_exposed_development_scope'})
                    for edge in declarations['actual_target_exposure']:
                        if edge['affected_task'] == task and edge['access_task'] in relevant:
                            reasons.append({'code': 'known_actual_target_exposure',
                                            'other': edge['access_task']})
                for other in sorted(against):
                    pair = tuple(sorted((task, other)))
                    b = biology.get(pair, {})
                    if kind == 'new_animal' and b.get('shared_animal') is True:
                        reasons.append({'code': 'declared_same_animal', 'other': other})
                    if kind in ('new_session', 'independent_acquisition') and b.get('shared_session') is True:
                        reasons.append({'code': 'declared_shared_session', 'other': other})
                    if kind == 'new_paper' and 'shared_exact_paper_locator' in edges.get(pair, set()):
                        reasons.append({'code': 'same_declared_paper_locator', 'other': other})
                status = 'contradicted' if reasons else 'unresolved'
                if not reasons:
                    reasons = [{'code': 'no_affirmative_identity_or_exposure_evidence'}]
            result['claims'].append({'kind': kind, 'against': sorted(against), 'status': status,
                                     'reasons': reasons})
        for other in sorted(compared - {task}):
            result['typed_direct_links'].append({'other': other,
                'relations': sorted(edges.get(tuple(sorted((task, other))), set())),
                'absence_means_independent': False})
        result['accepted'] = not result['operational_conflicts'] and all(
            c['status'] == 'compatible_development_only' for c in result['claims'])
        decisions.append(result)
    return {'schema': 'campaign_exposure_decision_v1',
            'status': 'compatible_development_selection' if all(r['accepted'] for r in decisions) else 'blocked',
            'accepted': all(r['accepted'] for r in decisions), 'decisions': decisions,
            'distinct_requested_tasks': len(seen), 'task_ids_merged': False,
            'graph_components_or_RL_split_computed': False,
            'readiness_or_execution_authorized': False,
            'history_independently_verified': False,
            'scope': 'Known declaration conflicts only; unresolved claims never certify independence. '
                     'Use separate requests for genuinely distinct operator contexts. No task is launched.'}


def references(request):
    """Task IDs whose current declarations can affect this exact request."""
    need(type(request) is dict and set(request) == {'schema', 'evaluations'}
         and request['schema'] == 'campaign_exposure_request_v1', 'request schema')
    rows = request['evaluations']
    need(type(rows) is list and 1 <= len(rows) <= 200, 'bounded task list')
    ids = set()
    for row in rows:
        need(type(row) is dict and set(row) == {'task_id', 'prior_access', 'concurrent_inputs', 'claims'},
             'exact evaluation keys')
        need(type(row['task_id']) is str, 'task ID string')
        ids.add(row['task_id'])
        lists = [row['prior_access'], row['concurrent_inputs']]
        claims = row['claims']
        need(type(claims) is list and 1 <= len(claims) <= len(KINDS), 'explicit bounded claims')
        for claim in claims:
            need(type(claim) is dict and set(claim) == {'kind', 'against'}, 'exact claim keys')
            lists.append(claim['against'])
        for values in lists:
            need(type(values) is list and len(values) <= 200 and all(type(x) is str for x in values),
                 'explicit task-ID list')
            ids.update(values)
    return ids


def load_source_bound(repo, here, source_sha, reader):
    need(type(source_sha) is str and re.fullmatch('[a-f0-9]{64}', source_sha), 'source SHA256')
    manifest_raw = reader.read(here/'SOURCE_MANIFEST.json', 32768)
    need(pin(manifest_raw)['sha256'] == source_sha, 'source manifest SHA256')
    manifest = parse(manifest_raw)
    bodies = {}
    for row in manifest['files']:
        name = row['path']
        need(type(name) is str and '/' not in name and name not in ('', '.', '..'), 'local source member')
        need(name not in bodies, 'unique source member')
        bodies[name] = reader.read(here / name if reader.view is not None else literal(here, name), 200000, row)
    need({'validate.py', 'LOCK.json', 'DECLARATIONS.json', 'POLICY.json'} <= set(bodies), 'exact runtime closure')
    lock, declarations = parse(bodies['LOCK.json']), parse(bodies['DECLARATIONS.json'])
    policy = parse(bodies['POLICY.json'])
    need(policy == POLICY and lock.get('bounded_admission_policy') == policy and reader.limit == policy['aggregate_bytes'], 'exact policy/LOCK/source equality')
    need(lock['source_read_cap_bytes'] == policy['aggregate_bytes']
         and lock['request_cap_bytes'] == policy['request_bytes']
         and lock['report_cap_bytes'] == policy['report_bytes'], 'legacy limits agree')
    need(manifest['policy'] == pin(bodies['POLICY.json'])
         and manifest['limits'] == {'report_bytes':policy['report_bytes'], 'request_bytes':policy['request_bytes'],
             'source_metadata_read_charge_bytes':policy['aggregate_bytes'], 'work_body_bytes':policy['work_body_bytes']},
         'manifest policy limits')
    return manifest, bodies, lock, declarations, pin(manifest_raw)

def load_bound(repo, here, source_sha, work_sha, reader, relevant_tasks):
    need(type(work_sha) is str and re.fullmatch('[a-f0-9]{64}', work_sha), 'WORK SHA256')
    manifest, bodies, lock, declarations, manifest_pin = load_source_bound(repo, here, source_sha, reader)
    audit_raw = reader.read(literal(repo, lock['audit']['path']), 250000, lock['audit'])
    reader.read(literal(repo, lock['builder']['path']), 20000, lock['builder'])
    work_raw = reader.read(literal(repo, lock['work_path']), POLICY['work_body_bytes'])
    need(pin(work_raw)['sha256'] == work_sha, 'fresh explicit WORK snapshot')
    work = parse(work_raw)
    audit = parse(audit_raw)
    need(set(work['preferred_sources']) == known_tasks(audit), 'exact canonical task set')
    need(type(relevant_tasks) is set and relevant_tasks and relevant_tasks <= known_tasks(audit),
         'known request task references')
    verified = []
    for task, facts in declarations['tasks'].items():
        if task not in relevant_tasks:
            continue
        descriptor = facts['selected_source']
        need(work['preferred_sources'][task] == descriptor['path'], 'selected task declaration path changed')
        raw = reader.read(literal(repo, descriptor['path']), 100000, descriptor)
        value = parse(raw)
        need(value['task_ids'] == [task], 'selected descriptor task binding')
        declaration = facts['declaration']
        rows = [x for x in value['files'] if x['source'] == declaration['path']]
        need(len(rows) == 1 and all(rows[0][k] == declaration[k] for k in ('bytes', 'sha256')),
             'declaration belongs to selected descriptor')
        reader.read(literal(repo, declaration['path']), 10000, declaration)
        verified.append(task)
    return audit, declarations, {'source_manifest': manifest_pin, 'audit': pin(audit_raw),
                                'work': pin(work_raw), 'verified_declaration_tasks': sorted(verified)}, lock


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--work-sha256', required=True)
    args = parser.parse_args(argv)
    reader = Reader()
    try:
        repo = args.repo.absolute()
        need(repo.is_dir() and not any(x.is_symlink() for x in (repo, *repo.parents)), 'ordinary repository')
        raw = reader.read(args.request, 131072)
        request = parse(raw)
        audit, declarations, evidence, lock = load_bound(
            repo, HERE, args.source_sha256, args.work_sha256, reader, references(request))
        need(len(raw) <= lock['request_cap_bytes'], 'selected request byte cap')
        report = assess(request, audit, declarations)
        report.update(evidence=evidence, request=pin(raw), metadata_read_charge_bytes=reader.used)
        output = (json.dumps(report, sort_keys=True, allow_nan=False, separators=(',', ':'))+'\n').encode()
        need(len(output) <= lock['report_cap_bytes'], 'bounded complete decision report')
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        return 0 if report['accepted'] else 2
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError) as error:
        # No submitted text, paths or target values are echoed from exception strings.
        print(json.dumps({'schema': 'campaign_exposure_error_v1', 'accepted': False,
                          'error_type': type(error).__name__, 'metadata_read_charge_bytes': reader.used}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
