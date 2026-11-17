"""Trusted offline scoring of four completed NEURAL-095 prediction artifacts.

No candidate code executes here. This is an arithmetic/validation component,
not a producer sandbox or proof of generation isolation, absence or matchedness.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys

sys.path.insert(0, str(Path(__file__).absolute().parent))
import numpy as np
import metrics
import paired
import validator

MODES = ('frozen_program', 'case_adaptive')
VIEWS = ('cue_only', 'neural')
CELLS = tuple(mode + '__' + view for mode in MODES for view in VIEWS)


def need(value, message):
    if not value:
        raise ValueError(message)


def strict_json(body):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    def bad_constant(value):
        raise ValueError('Nonfinite JSON')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad_constant)


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_nlink)


def snapshot(path, cap):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'Unlinked file and ancestors required')
    st = path.stat()
    need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and 0 < st.st_size <= cap, 'Bounded ordinary file required')
    with path.open('rb') as stream:
        need(identity(os.fstat(stream.fileno())) == identity(st), 'File changed before opening')
        body = stream.read(cap + 1)
        need(identity(os.fstat(stream.fileno())) == identity(st), 'File changed during capture')
    need(len(body) == st.st_size, 'Complete bounded file required')
    need(all(not p.is_symlink() for p in (path, *path.parents))
         and identity(path.stat()) == identity(st), 'File path changed during capture')
    return body, identity(st)


def read(path, cap):
    return snapshot(path, cap)[0]


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def pinned(path, expected):
    need(set(expected) == {'bytes', 'sha256'} and type(expected['bytes']) is int
         and 0 < expected['bytes'] <= 100000, 'Exact bounded artifact descriptor')
    body = read(path, expected['bytes'])
    need(pin(body) == expected, 'Artifact identity mismatch: ' + Path(path).name)
    return body


def capture_public(submissions, ids):
    need(set(submissions) == set(CELLS), 'Exactly four mode/view submissions required')
    need(len(ids) == 258 and validator.public_ids(ids) == ids, 'Original complete 258-case identity required')
    vectors, pins = {}, {}
    for cell in CELLS:
        before, before_identity = snapshot(submissions[cell], validator.MAX_FILE_BYTES)
        vectors[cell] = validator.validate(submissions[cell], ids)
        after, after_identity = snapshot(submissions[cell], validator.MAX_FILE_BYTES)
        need(after == before and after_identity == before_identity, 'Submission changed around validation')
        pins[cell] = pin(before)
    return vectors, pins


def score_captured(vectors, ids, private_loader, references):
    """Private loader is called only after complete public capture has returned."""
    need(set(vectors) == set(CELLS) and len(ids) == 258, 'All captured cells required')
    value = private_loader()
    need(isinstance(value, dict) and set(value) == {'case_id', 'tp_ms', 'condition', 'context'}
         and np.asarray(value['case_id']).tolist() == ids, 'Private/public exact identity join')
    result = {}
    for mode in MODES:
        arms = {view: metrics.score_candidate(vectors[mode + '__' + view], lambda: value, references)
                for view in VIEWS}
        difference = paired.pair_difference(vectors[mode + '__cue_only'], vectors[mode + '__neural'],
            value['tp_ms'], value['condition'], value['context'])
        diagnostics = paired.verify_paired_arithmetic(difference, arms['cue_only']['candidate'], arms['neural']['candidate'])
        result[mode] = {'arms': arms, 'paired': difference, 'paired_arithmetic_checks': len(diagnostics)}
    return {'candidate_id': 'NEURAL-095', 'status': 'four_cell_predictions_scored', 'modes': result,
            'cases_per_cell': 258, 'private_loader_calls': 1, 'new_reference_fits': 0,
            'candidate_fit_count': 'not measured by arithmetic scorer',
            'matched_method_proven': False, 'research_qualified': False,
            'candidate_code_executed': False, 'generation_isolation_verified': False,
            'producer_absence_verified': False, 'cross_mode_causal_comparison_claimed': False}


def evaluate(submissions, ids, private_loader, reference_loader):
    vectors, pins = capture_public(submissions, ids)
    references = reference_loader()
    result = score_captured(vectors, ids, private_loader, references)
    result['submission_identities'] = pins
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--submission', action='append', required=True, help='mode__view=/absolute/submission.npz (four)')
    args = parser.parse_args()
    rows = [s.split('=', 1) for s in args.submission]
    need(len(rows) == 4 and all(len(r) == 2 for r in rows) and len({r[0] for r in rows}) == 4,
         'Four unique named submission paths required')
    artifacts = strict_json(read(Path(__file__).parent / 'artifacts.json', 10000))
    need(artifacts['candidate_id'] == 'NEURAL-095' and artifacts['cases'] == 258, 'Original task artifact manifest')
    files = artifacts['files']
    identity = strict_json(pinned(args.data_dir / 'public_identity.json', files['public_identity.json']))
    need(set(identity) == {'schema_version', 'case_id'} and type(identity['schema_version']) is int
         and identity['schema_version'] == 1, 'Exact public identity envelope')
    ids = identity['case_id']
    def reference_loader():
        grade = strict_json(pinned(args.data_dir / 'reference_grade.json', files['reference_grade.json']))
        commit = strict_json(pinned(args.data_dir / 'reference_commit.json', files['reference_commit.json']))
        audit = strict_json(pinned(args.data_dir / 'reference_audit.json', files['reference_audit.json']))
        need(commit['status'] == 'producer_removed_outputs_committed' and commit['all_owned_producers_absent'] is True,
             'Accepted reference production and commitment required')
        need(commit['predictions'] == artifacts['reference_prediction_identity']
             and commit['public_identity'] == files['public_identity.json']
             and commit['private_targets'] == files['query_targets.npz'], 'Reference input/output identity')
        need(grade['status'] == 'continuous_fixed_reference_panel_scored' and grade['candidate_id'] == 'NEURAL-095'
             and grade['public_validation_before_private_decode'] is True and grade['private_loader_invocations'] == 1
             and grade['predictions'] == commit['predictions'] and set(grade['scores']) == set(metrics.METHODS),
             'All five original fixed references required')
        need(audit['status'] == 'passed' and audit['independent_scalar_checks'] == 280
             and audit['score_sha256'] == files['reference_grade.json']['sha256'], 'Reference arithmetic audit identity')
        return grade
    def private_loader():
        body = pinned(args.data_dir / 'query_targets.npz', files['query_targets.npz'])
        with np.load(io.BytesIO(body), allow_pickle=False) as archive:
            return {key: archive[key] for key in archive.files}
    print(json.dumps(evaluate(dict(rows), ids, private_loader, reference_loader), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
