"""Private offline grading CLI; no candidate execution, fitting or acquisition.

Only invoke after prediction commitment. All ten public predictions validate
before any target body is read. Operator retains private source and targets.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'public'))
from interface import ContractError, decode_json, validate_case, validate_prediction
from scorer import score_case, aggregate_panel


def read_regular(path, limit):
    p = Path(path)
    if p.is_symlink():
        raise ValueError('symlink input not permitted')
    s = p.stat()
    if not stat.S_ISREG(s.st_mode) or not 0 < s.st_size <= limit:
        raise ValueError('bounded ordinary file required')
    with p.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) != s.st_size or len(raw) > limit:
        raise ValueError('input size changed')
    return raw


def descriptor_read(root, d, limit):
    if type(d) is not dict or set(d) != {'path', 'bytes', 'sha256'}:
        raise ValueError('exact descriptor keys required')
    rel = Path(d['path'])
    if rel.is_absolute() or '..' in rel.parts or str(rel) != d['path']:
        raise ValueError('safe relative descriptor path required')
    base = Path(root).resolve(strict=True)
    p = base / rel
    cursor = base
    for part in rel.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError('linked descriptor path inside root not permitted')
    raw = read_regular(p, limit)
    if type(d['bytes']) is not int or len(raw) != d['bytes'] or hashlib.sha256(raw).hexdigest() != d['sha256']:
        raise ValueError('descriptor identity mismatch')
    return raw


def grade(public_manifest, predictions_dir, private_manifest):
    public_path = Path(public_manifest)
    pub = decode_json(read_regular(public_path, 1024 * 1024))
    if type(pub) is not dict or set(pub) != {'schema', 'cases'} or pub['schema'] != 'neural055-public-panel-v1' or type(pub['cases']) is not list or len(pub['cases']) != 10:
        raise ValueError('complete public panel manifest required')
    cases = [validate_case(decode_json(descriptor_read(public_path.parent, x, 1024 * 1024))) for x in pub['cases']]
    case_ids = [c['case_id'] for c in cases]
    if len(set(case_ids)) != 10:
        raise ValueError('ten unique public cases required')
    expected_names = {x + '.json' for x in case_ids}
    try:
        observed_names = {p.name for p in Path(predictions_dir).iterdir()}
    except (OSError, ValueError) as exc:
        raise ContractError('prediction directory is unreadable') from exc
    if observed_names != expected_names:
        raise ContractError('complete exact prediction-file roster required')
    predictions = []
    for case in cases:
        try:
            raw = read_regular(Path(predictions_dir) / (case['case_id'] + '.json'), 4 * 1024 * 1024)
        except (OSError, ValueError) as exc:
            raise ContractError('submitted prediction file is unreadable or outside transport bounds') from exc
        pred = decode_json(raw)
        validate_prediction(case, pred, row_sum_abs_tolerance=1e-6)
        predictions.append(pred)
    # No target manifest/body before full public validation above.
    private_path = Path(private_manifest)
    private = decode_json(read_regular(private_path, 1024 * 1024))
    if type(private) is not dict or set(private) != {'schema', 'cases'} or private['schema'] != 'neural055-private-panel-v1' or type(private['cases']) is not dict or set(private['cases']) != set(case_ids):
        raise ValueError('complete private panel manifest required')
    reports = []
    for case, pred in zip(cases, predictions):
        def target_loader(case_id=case['case_id']):
            return decode_json(descriptor_read(private_path.parent, private['cases'][case_id], 1024 * 1024))
        try:
            report = score_case(case, pred, target_loader, row_sum_abs_tolerance=1e-6,
                                independent_tie_order=case['candidate_ids'], log_loss_policy='natural_log_no_clipping')
        except ContractError as exc:
            raise ValueError('private operator target/schema configuration invalid') from exc
        reports.append(report)
    return {'schema': 'neural055-private-grade-v1', 'policy': 'prospective_draft1',
            'panel': aggregate_panel(reports, expected_case_ids=case_ids), 'cases': reports,
            'calibration_provenance': 'not_established_by_numerical_score',
            'acceptance_or_qualification_claim': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-panel', required=True)
    parser.add_argument('--predictions', required=True)
    parser.add_argument('--private-panel', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        raise ValueError('fresh output path required')
    try:
        result = grade(args.public_panel, args.predictions, args.private_panel)
    except ContractError as exc:
        result = {'status': 'invalid_submission', 'reason': str(exc), 'score': None}
        code = 2
    else:
        code = 0
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
