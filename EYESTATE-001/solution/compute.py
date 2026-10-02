"""Offline source-bound ABIDE released eye-protocol prediction.

No inferential biological eye-state claim: site-shared and unseen-site CV are
different descriptive prediction questions. All source and method checks precede
numerics. Importing this module performs no source access or output writes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import stat
import sys
import warnings

import numpy as np
import scipy
import sklearn
from scipy.linalg import cholesky, solve_triangular
from scipy.optimize import lsq_linear
from sklearn.covariance import LedoitWolf
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

TASK_ID = "EYESTATE-001"
METHOD_SHA256 = "2cc71a311a25ec5de5bf14d5e2d10097b7e609eba93ea8be273f63f7de08a4a0"
SOURCE_SHA256 = "d4e930b84667e58831880100039cde688d56ccd0ff8c509f0f363fd1c4685aeb"
METHOD_ID = "abide-lw-site-random-squared-hinge-certificate-v4"
DATASET = "ABIDE_pcp/cpac/filt_noglobal/rois_cc200"
EPS = np.finfo(np.float64).eps


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def safe_path(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), "Symlink path or ancestor refused")
    return path.resolve(strict=False)


def regular(path):
    path = safe_path(path)
    require(stat.S_ISREG(path.stat().st_mode), "Regular input file required")
    return path


def disjoint(a, b):
    require(a != b and a not in b.parents and b not in a.parents, "Source/evidence paths overlap")


def prepare_destinations(data_dir, method_path, output_dir, private_dir=None):
    data, method, output = map(safe_path, (data_dir, method_path, output_dir))
    private = safe_path(private_dir) if private_dir is not None else None
    for destination in [output] + ([private] if private else []):
        disjoint(destination, data)
        disjoint(destination, method)
        require(not destination.exists() or destination.is_dir() and not any(destination.iterdir()),
                "Evidence destination must be new or empty")
    if private:
        disjoint(output, private)
    # Complete validation first: never create evidence inside an unsafe input root.
    output.mkdir(parents=True, exist_ok=True)
    if private:
        private.mkdir(parents=True, exist_ok=True)
    return data, method, output, private


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def write_csv(path, columns, rows):
    with Path(path).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_npz(path, **arrays):
    with Path(path).open("xb") as stream:
        np.savez_compressed(stream, **arrays)


def strict_integer(value):
    number = Decimal(str(value))
    require(number.is_finite() and number == number.to_integral_value(), "Invalid original integer")
    return int(number)


def load_inputs(data_dir, method_path):
    method_path = regular(method_path)
    raw = method_path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == METHOD_SHA256, "Whole method contract hash mismatch")
    method = json.loads(raw)
    local = Path(__file__).resolve().parents[1] / "environment" / "stage_source.py"
    helper = local if local.is_file() else Path("/opt/source/stage_source.py")
    spec = importlib.util.spec_from_file_location("eyestate_original_stager", regular(helper))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = module.verify_staged(data_dir)
    require(module.MANIFEST_SHA256 == SOURCE_SHA256 and method["source"]["manifest_sha256"] == SOURCE_SHA256,
            "Source/method identity mismatch")
    require(method["method_id"] == METHOD_ID, "Wrong public method")
    return method, manifest


def standardized_source(values):
    values = np.asarray(values, dtype=np.float64)
    require(values.ndim == 2 and values.shape[0] > 1 and values.shape[1] > 1 and np.isfinite(values).all(),
            "Finite two-dimensional source time series required")
    centered = values - values.mean(axis=0)
    sd = centered.std(axis=0, ddof=0)
    low = sd < EPS
    sd[low] = 1.0
    return centered / sd, int(np.all(values == values[0], axis=0).sum()), int(low.sum())


def connectivity(values):
    standardized, n_constant, n_low_sd = standardized_source(values)
    covariance = LedoitWolf(store_precision=False, assume_centered=False, block_size=1000).fit(standardized)
    matrix = covariance.covariance_
    diagonal = np.diag(matrix)
    require(np.isfinite(matrix).all() and np.all(diagonal > 0), "Undefined covariance: nonpositive diagonal")
    corr = matrix / np.sqrt(diagonal[:, None] * diagonal[None, :])
    shrinkage = float(covariance.shrinkage_)
    require(np.isfinite(corr).all() and np.max(np.abs(corr)) <= 1 + 1e-12 and 0 <= shrinkage <= 1,
            "Invalid Ledoit-Wolf correlation or shrinkage")
    indices = np.tril_indices(values.shape[1], k=-1)
    return corr[indices], shrinkage, n_constant, n_low_sd


def read_source(data_dir, manifest, method):
    entries = {e["phenotype_row_index"]: e for e in manifest["files"] if e["role"] == "roi_timeseries"}
    phenotype = next(e for e in manifest["files"] if e["role"] == "phenotype")
    with regular(data_dir / phenotype["path"]).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        require(len(reader.fieldnames) == len(set(reader.fieldnames)), "Duplicate phenotype columns")
        original = list(reader)
    require(len(original) == method["source"]["phenotype_rows"], "Original phenotype row count changed")
    ledger, selected, features, shrinkages, seen = [], [], [], [], set()
    expected_header = "\t".join("#" + str(i) for i in range(1, 201))
    for row_index, original_row in enumerate(original):
        subject = strict_integer(original_row["SUB_ID"])
        eye = strict_integer(original_row["EYE_STATUS_AT_SCAN"])
        file_id, site = original_row["FILE_ID"], original_row["SITE_ID"]
        require(subject not in seen and site and file_id, "Duplicate/missing source identity")
        seen.add(subject)
        item = dict(phenotype_row=row_index, subject_id=subject, file_id=file_id, site=site,
                    eye_code=eye, label=1 if eye == 1 else 0 if eye == 2 else None,
                    source_path=None, source_sha256=None, n_timepoints=None, n_rois=None,
                    n_constant_rois=None, n_low_sd_rois=None, included=False,
                    exclusion_reason="unavailable_derivative", selected_index=None)
        if file_id == "no_filename":
            require(row_index not in entries, "Unexpected ROI for unavailable derivative")
        else:
            entry = entries.get(row_index)
            require(entry is not None and int(entry["subject_id"]) == subject and entry["file_id"] == file_id,
                    "Original phenotype/ROI identity mismatch")
            require(eye in (1, 2), "Invalid selected source eye label")
            path = regular(data_dir / entry["path"])
            with path.open(encoding="utf-8") as stream:
                header = stream.readline().rstrip("\r\n")
            require(header == expected_header and hashlib.sha256(header.encode()).hexdigest() ==
                    method["source"]["roi_header_sha256"], "Original ROI column header mismatch")
            values = np.loadtxt(path, dtype=np.float64, comments="#", ndmin=2)
            require(values.shape[1] == 200 and 78 <= values.shape[0] <= 316 and np.isfinite(values).all(),
                    "Original ROI shape/nonfinite precondition failed")
            feature, shrinkage, constant, low = connectivity(values)
            item.update(source_path=entry["path"], source_sha256=entry["sha256"],
                        n_timepoints=int(values.shape[0]), n_rois=200, n_constant_rois=constant,
                        n_low_sd_rois=low, included=True, exclusion_reason="included",
                        selected_index=len(selected))
            selected.append(item)
            features.append(feature)
            shrinkages.append(shrinkage)
            if len(selected) % 50 == 0:
                print(f"Source connectivity complete: {len(selected)}", flush=True)
        ledger.append(item)
    require(len(selected) == method["source"]["known_named_derivatives"] and
            len(ledger) - len(selected) == method["source"]["known_no_filename_rows"], "Frozen cohort changed")
    return ledger, selected, np.asarray(features, dtype=np.float64), np.asarray(shrinkages)


def split_plan(y, sites):
    y, sites = np.asarray(y, dtype=int), np.asarray(sites)
    require(set(y.tolist()) == {0, 1} and min(np.bincount(y)) >= 10, "Two-class stratification support required")
    splits = []
    for fold, site in enumerate(sorted(set(sites.tolist()))):
        test = np.flatnonzero(sites == site)
        train = np.flatnonzero(sites != site)
        splits.append(("loso", fold, site, train, test))
    for fold, (train, test) in enumerate(StratifiedKFold(10, shuffle=True, random_state=0).split(np.zeros(len(y)), y)):
        splits.append(("random10", fold, None, train, test))
    for _, _, _, train, test in splits:
        require(len(test) > 0 and set(y[train].tolist()) == {0, 1}, "Empty test or single-class training fold")
    return splits


def confusion(y, prediction):
    y, prediction = np.asarray(y, dtype=int), np.asarray(prediction, dtype=int)
    counts = {name: int(np.sum((y == truth) & (prediction == guessed)))
              for name, truth, guessed in (("tn", 0, 0), ("fp", 0, 1), ("fn", 1, 0), ("tp", 1, 1))}
    positive, negative = counts["tp"] + counts["fn"], counts["tn"] + counts["fp"]
    opened = counts["tp"] / positive if positive else None
    closed = counts["tn"] / negative if negative else None
    supported = [value for value in (opened, closed) if value is not None]
    return dict(counts, open_recall=opened, closed_recall=closed,
                balanced_accuracy=float(np.mean(supported)) if supported else None)


def certificate(z, y, coefficient, intercept):
    t = 2 * np.asarray(y, dtype=np.float64) - 1
    h = np.maximum(0.0, 1 - t * (z @ coefficient + intercept))
    alpha = 2 * h
    gradient = coefficient - z.T @ (t * alpha)
    gradient_intercept = intercept - np.sum(t * alpha)
    primal = 0.5 * (coefficient @ coefficient + intercept ** 2) + h @ h
    gap = 0.5 * (gradient @ gradient + gradient_intercept ** 2)
    require(np.isfinite([primal, gap]).all(), "Nonfinite objective/certificate")
    return float(primal), float(gap), float(1e-6 * (1 + primal))


def bvls_dual(z, y):
    """Exact C1 squared-hinge dual, including the penalized synthetic intercept."""
    signed = 2 * np.asarray(y, dtype=np.float64) - 1
    gram = (z @ z.T + 1.0) * signed[:, None] * signed[None, :]
    gram[np.diag_indices(len(y))] += 0.5
    lower = cholesky(gram, lower=True, check_finite=True)
    target = solve_triangular(lower, np.ones(len(y)), lower=True, check_finite=True)
    return lsq_linear(lower.T, target, bounds=(0, np.inf), method='bvls',
                      tol=1e-12, max_iter=30000, lsq_solver='exact')


def fit_fold(x, y, split, private_dir=None):
    scheme, fold, site, train, test = split
    scaler = StandardScaler(with_mean=True, with_std=True)
    z = scaler.fit_transform(x[train])
    z_test = scaler.transform(x[test])
    require(np.isfinite(z).all() and np.isfinite(z_test).all() and np.all(scaler.var_ >= 0) and
            np.all(scaler.scale_ > 0), "Invalid training-only scaler")
    scaler_state = dict(scaler_mean=scaler.mean_, scaler_variance=scaler.var_, scaler_scale=scaler.scale_)
    solver_state, candidate, stage = {}, {}, 'dual_factorization_or_solver'
    def failed_checkpoint(error, captured):
        if private_dir is not None:
            diagnostic = dict(scheme=scheme, fold_id=fold, stage=stage, status='failed_precondition',
                reason=f'{type(error).__name__}: {str(error) or type(error).__name__}',
                warnings=[dict(category=w.category.__name__, message=str(w.message)) for w in captured], **solver_state)
            write_npz(private_dir / f'fold_{scheme}_{fold:02d}.npz', train_indices=train, test_indices=test,
                      **scaler_state, **candidate, diagnostics_json=np.asarray(json.dumps(diagnostic, allow_nan=False)))
    captured = []
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            fitted = bvls_dual(z, y[train])
            raw_alpha = np.asarray(fitted.x, dtype=np.float64).copy()
            candidate['raw_dual_alpha'] = raw_alpha
            solver_state.update(solver_success=bool(fitted.success), solver_status=int(fitted.status),
                                solver_message=str(fitted.message), n_iter=int(fitted.nit))
            stage = 'candidate_certificate_or_decision'
            require(raw_alpha.shape == (len(train),) and np.isfinite(raw_alpha).all(),
                    'Wrong shape or nonfinite raw dual candidate')
            # Frozen v4 feasibility step; the unmodified optimizer return remains evidence.
            # This projection is not an optimality claim: the primal certificate still gates.
            alpha = np.maximum(raw_alpha, 0)
            projection_delta = alpha - raw_alpha
            candidate.update(dual_alpha=alpha, dual_projection_delta=projection_delta)
            solver_state.update(n_raw_negative=int(np.sum(raw_alpha < 0)), min_raw_alpha=float(raw_alpha.min()),
                                max_projection_change=float(projection_delta.max()))
            signed = 2 * y[train] - 1
            coefficient, intercept = z.T @ (signed * alpha), float(np.sum(signed * alpha))
            candidate.update(coefficient=coefficient, intercept=intercept)
            require(np.isfinite(alpha).all() and np.all(alpha >= 0), 'Invalid projected dual candidate')
            require(np.isfinite(coefficient).all() and np.isfinite(intercept), 'Nonfinite fitted candidate')
            primal, gap, limit = certificate(z, y[train], coefficient, intercept)
            decisions = z_test @ coefficient + intercept
            require(np.isfinite(decisions).all(), "Nonfinite held-out decision")
    except Exception as error:
        failed_checkpoint(error, captured)
        for warning in captured:
            warnings.warn(warning.message, warning.category)
        raise
    warning_records = [{"category": warning.category.__name__, "message": str(warning.message)} for warning in captured]
    for warning in captured:
        warnings.warn(warning.message, warning.category)
    n_iter = solver_state['n_iter']
    model = dict(scaler_mean=scaler.mean_, scaler_variance=scaler.var_, scaler_scale=scaler.scale_,
                 coefficient=coefficient, intercept=intercept)
    diagnostics = dict(scheme=scheme, fold_id=fold, primal_objective=primal, certificate_gap=gap,
                       certificate_limit=limit, warnings=warning_records, **solver_state)
    if private_dir is not None:
        write_npz(private_dir / f"fold_{scheme}_{fold:02d}.npz", train_indices=train, test_indices=test,
                  decision_score=decisions, raw_dual_alpha=raw_alpha, dual_alpha=alpha,
                  dual_projection_delta=projection_delta, **model,
                  diagnostics_json=np.asarray(json.dumps(diagnostics, allow_nan=False)))
    require(solver_state['solver_success'] and solver_state['solver_status'] > 0 and
            0 <= n_iter < 30000 and not captured,
            f"Reference convergence failure: {scheme}/{fold}, diagnostics={diagnostics}")
    require(gap <= limit, f"Public objective certificate failed: {scheme}/{fold}, gap={gap}, limit={limit}")
    # Optional supplied-reference diagnostics survive even without PRIVATE_DIR.
    # The second axis is the complete canonical selected-person axis, not train order.
    raw_padded, projected_padded = np.zeros(len(y)), np.zeros(len(y))
    training_mask = np.zeros(len(y), dtype=bool)
    raw_padded[train], projected_padded[train], training_mask[train] = raw_alpha, alpha, True
    model.update(oracle_raw_dual_alpha_by_selected_index=raw_padded,
                 oracle_projected_dual_alpha_by_selected_index=projected_padded,
                 oracle_dual_training_mask=training_mask)
    prediction = (decisions > 0).astype(int)
    majority = int(np.sum(y[train] == 1) >= np.sum(y[train] == 0))
    bound = len(train) * EPS * scaler.var_ + (len(train) * scaler.mean_ * EPS) ** 2
    row = dict(scheme=scheme, fold_id=fold, held_out_site=site, n_train=len(train), n_test=len(test),
               n_train_open=int(np.sum(y[train] == 1)), n_train_closed=int(np.sum(y[train] == 0)),
               n_test_open=int(np.sum(y[test] == 1)), n_test_closed=int(np.sum(y[test] == 0)),
               **confusion(y[test], prediction), training_majority_prediction=majority,
               n_constant_features=int(np.sum(scaler.var_ <= bound)), primal_objective=primal,
               certificate_gap=gap, certificate_limit=limit, solver="scipy.optimize.lsq_linear/bvls",
               solver_status=f'{fitted.status}: {fitted.message}', n_iter=n_iter)
    return model, row, decisions, prediction, warning_records


def observed_source(ledger, selected, n_features):
    sites = sorted({row['site'] for row in selected})
    def histogram(field, public_field):
        return [{public_field: value, 'n_subjects': count}
                for value, count in sorted(Counter(row[field] for row in selected).items())]
    return dict(n_phenotype_rows=len(ledger), n_no_filename=len(ledger) - len(selected),
                n_named_derivatives=len(selected), n_selected=len(selected), n_features=n_features,
                selected_site_ids=sites,
                site_support=[dict(site=site, n_open=sum(r['site'] == site and r['label'] == 1 for r in selected),
                                   n_closed=sum(r['site'] == site and r['label'] == 0 for r in selected)) for site in sites],
                frame_count_histogram=histogram('n_timepoints', 'n_timepoints'),
                roi_count_histogram=histogram('n_rois', 'n_rois'),
                constant_roi_count_histogram=histogram('n_constant_rois', 'n_constant_rois'),
                source_column_convention='header_numbered_1_to_200_source_order')


def summarize(ledger, selected, predictions, folds, n_features, pilot=False):
    schemes = {}
    for scheme in ('loso', 'random10'):
        rows = [r for r in predictions if r['scheme'] == scheme]
        per_fold = [r for r in folds if r['scheme'] == scheme]
        truth = [r['label'] for r in rows]
        score = confusion(truth, [r['prediction'] for r in rows])
        pooled = score.pop('balanced_accuracy')
        schemes[scheme] = dict(score, n_folds=len(per_fold), pooled_balanced_accuracy=pooled,
            equal_fold_mean_recall=float(np.mean([r['balanced_accuracy'] for r in per_fold])) if per_fold else None,
            training_majority_pooled_balanced_accuracy=confusion(truth,
                [r['training_majority_prediction'] for r in rows])['balanced_accuracy'])
    sites = sorted({r['site'] for r in selected})
    single = sum(len({r['label'] for r in selected if r['site'] == site}) == 1 for site in sites)
    y = np.asarray([r['label'] for r in selected])
    result = dict(status='resource_pilot' if pilot else 'ok', method_id=METHOD_ID,
        cv_balanced_accuracy=None if pilot else schemes['loso']['pooled_balanced_accuracy'],
        site_blocked_balanced_accuracy=None if pilot else schemes['loso']['pooled_balanced_accuracy'],
        random_kfold_balanced_accuracy=None if pilot else schemes['random10']['pooled_balanced_accuracy'],
        legacy_equal_site_mean_recall=None if pilot else schemes['loso']['equal_fold_mean_recall'],
        site_only_unseen_site_baseline=None if pilot else schemes['loso']['training_majority_pooled_balanced_accuracy'],
        always_open_pooled_balanced_accuracy=confusion(y, np.ones(len(y), int))['balanced_accuracy'],
        always_closed_pooled_balanced_accuracy=confusion(y, np.zeros(len(y), int))['balanced_accuracy'],
        n_source_rows=len(ledger), n_unavailable_derivatives=len(ledger) - len(selected),
        n_subjects=len(selected), n_features=n_features, n_sites=len(sites),
        n_eyes_open=int(np.sum(y == 1)), n_eyes_closed=int(np.sum(y == 0)),
        single_class_sites=single, mixed_class_sites=len(sites) - single, chance=0.5, schemes=schemes)
    if pilot:
        result['resource_pilot_scope'] = dict(features='all_selected_original_subjects',
            fitted_models=[dict(scheme='loso', fold_id=0, held_out_site='CALTECH')],
            incomplete_full_cohort_cv=True)
    return result


def run(data_dir, method_path, output_dir, private_dir=None, pilot_fold=None):
    method, manifest = load_inputs(data_dir, method_path)
    ledger, selected, x, shrinkage = read_source(data_dir, manifest, method)
    y, sites = np.asarray([r['label'] for r in selected]), np.asarray([r['site'] for r in selected])
    plan = split_plan(y, sites)
    if pilot_fold is not None:
        require(pilot_fold == 'CALTECH' and plan[0][:3] == ('loso', 0, 'CALTECH'), 'Only predeclared CALTECH pilot allowed')
        plan = plan[:1]
    axes = np.tril_indices(method['features']['n_rois'], k=-1)
    require(x.shape == (len(selected), len(axes[0])) and np.isfinite(x).all(), 'Feature axis mismatch')
    feature_arrays = dict(phenotype_row=np.asarray([r['phenotype_row'] for r in selected], dtype=np.int64),
        subject_id=np.asarray([r['subject_id'] for r in selected], dtype=np.int64),
        feature_index=np.arange(x.shape[1], dtype=np.int64), roi_i=axes[0], roi_j=axes[1],
        correlation=x, shrinkage=shrinkage)
    # Source-feature evidence precedes any model; failed fits preserve these bytes.
    write_csv(output_dir / 'cohort.csv', method['artifacts']['cohort.csv']['columns'], ledger)
    write_npz(output_dir / 'features.npz', **feature_arrays)
    models, fold_rows, predictions, fit_warnings = [], [], [], []
    for split in plan:
        scheme, fold, site, train, test = split
        print(f'Fitting {scheme}/{fold}: train={len(train)}, test={len(test)}, site={site}', flush=True)
        model, fold_row, decision, prediction, captured = fit_fold(x, y, split, private_dir)
        models.append(model); fold_rows.append(fold_row)
        fit_warnings.append(dict(scheme=scheme, fold_id=fold, warnings=captured))
        for k, index in enumerate(test):
            source = selected[index]
            predictions.append(dict(scheme=scheme, phenotype_row=source['phenotype_row'],
                subject_id=source['subject_id'], site=source['site'], label=int(y[index]),
                fold_id=fold, held_out_site=site, decision_score=float(decision[k]),
                prediction=int(prediction[k]), training_majority_prediction=fold_row['training_majority_prediction']))
        print(f'Completed {scheme}/{fold}: certificate={fold_row["certificate_gap"]:.9g} <= '
              f'{fold_row["certificate_limit"]:.9g}; n_iter={fold_row["n_iter"]}', flush=True)
    model_arrays = {key: np.asarray([m[key] for m in models]) for key in models[0]}
    model_arrays.update(scheme=np.asarray([s[0] for s in plan]), fold_id=np.asarray([s[1] for s in plan]),
                        feature_index=feature_arrays['feature_index'],
                        oracle_dual_phenotype_row=feature_arrays['phenotype_row'],
                        oracle_dual_subject_id=feature_arrays['subject_id'])
    write_npz(output_dir / 'fold_models.npz', **model_arrays)
    for filename, rows in (('oof_predictions.csv', predictions), ('per_fold.csv', fold_rows)):
        write_csv(output_dir / filename, method['artifacts'][filename]['columns'], rows)
    result = summarize(ledger, selected, predictions, fold_rows, x.shape[1], pilot_fold is not None)
    metadata = dict(status=result['status'], task_id=TASK_ID, method_id=METHOD_ID,
        method_contract_sha256=METHOD_SHA256, source_manifest_sha256=SOURCE_SHA256,
        source_sha256={e['path']: e['sha256'] for e in manifest['files']}, dataset_id=DATASET,
        source_observed=observed_source(ledger, selected, x.shape[1]),
        software_versions=dict(python=platform.python_version(), numpy=np.__version__,
                               scipy=scipy.__version__, scikit_learn=sklearn.__version__), fit_warnings=fit_warnings)
    metadata['reference_diagnostics'] = {
        'scope': 'Optional supplied-reference evidence, not mandatory participant fields or extra acceptance gates.',
        'artifact': 'fold_models.npz',
        'arrays': ['oracle_raw_dual_alpha_by_selected_index', 'oracle_projected_dual_alpha_by_selected_index',
                   'oracle_dual_training_mask', 'oracle_dual_phenotype_row', 'oracle_dual_subject_id'],
        'axes': 'Dual matrices and Boolean training mask are model-by-canonical-selected-person. '
                'Model keys are scheme/fold_id; person keys are oracle_dual_phenotype_row and oracle_dual_subject_id, '
                'identical to canonical features.npz person axes.',
        'padding': 'Held-out entries have mask=false and both dual coefficients filled with zero; '
                   'these are padding, not fitted values. Training entries preserve raw optimizer return and max(raw,0).',
        'optimality': 'Raw optimizer status is in per_fold.csv; neither raw success nor projection replaces '
                      'the independently recomputed primal-derived objective certificate.'}
    if pilot_fold is not None:
        metadata['resource_pilot_scope'] = result['resource_pilot_scope']
    # Complete markers are written last, after all required primitive/model evidence.
    with (output_dir / 'findings.md').open('x', encoding='utf-8') as stream:
        stream.write('# Released ABIDE eye-protocol prediction\n\n')
        if pilot_fold is not None:
            stream.write('Resource pilot only: all source features, CALTECH LOSO fold 0 only. '
                         'Full-cohort CV and random-CV summaries are undefined.\n\n')
        else:
            stream.write(f"Pooled unseen-site balanced accuracy: {result['cv_balanced_accuracy']:.9g}. "
                f"Site-shared random-CV pooled balanced accuracy: {result['random_kfold_balanced_accuracy']:.9g}. "
                f"Equal-site mean recall: {result['legacy_equal_site_mean_recall']:.9g}; this is a different estimand. "
                f"Unseen-site training-majority baseline: {result['site_only_unseen_site_baseline']:.9g}.\n\n")
        stream.write(f"All {len(selected)} released derivatives were retained; "
            f"{sum(r['n_constant_rois'] > 0 for r in selected)} people have at least one constant ROI column. "
            'This unfiltered cohort is not uniformly adequate brain coverage. Eye protocol is strongly associated '
            'with acquisition site; unseen-site prediction does not identify a biological or causal eye-state effect. '
            'No uncertainty, null-inference or label-permutation test was performed. The two split designs address '
            'different descriptive prediction questions, without a required score ordering.\n')
    write_json(output_dir / 'run_metadata.json', metadata)
    write_json(output_dir / 'eye_decoding_results.json', result)
    if private_dir is not None:
        write_json(private_dir / 'completion.json', dict(status=result['status'], method_contract_sha256=METHOD_SHA256,
            source_manifest_sha256=SOURCE_SHA256, n_completed_folds=len(plan), fit_warnings=fit_warnings))
    return result


def failure_evidence(output, error):
    reason = f'{type(error).__name__}: {str(error) or type(error).__name__}'
    payload = dict(status='failed_precondition', reason=reason, method_id=METHOD_ID,
                   task_id=TASK_ID, method_contract_sha256=METHOD_SHA256, source_manifest_sha256=SOURCE_SHA256)
    # Authoritative late-failure receipt even if a preceding complete marker exists.
    write_json(output / 'failure_report.json', payload)
    for filename in ('eye_decoding_results.json', 'run_metadata.json'):
        if not (output / filename).exists():
            write_json(output / filename, payload)
    if not (output / 'findings.md').exists():
        with (output / 'findings.md').open('x', encoding='utf-8') as stream:
            stream.write('# Analysis failed\n\n' + reason + '\nNo complete prediction result was produced.\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default=os.environ.get('SOURCE_DIR', '/app/data/eyestate'))
    parser.add_argument('--method-contract', default=os.environ.get('METHOD_CONTRACT', '/app/method_contract.json'))
    parser.add_argument('--output-dir', default=os.environ.get('OUTPUT_DIR', '/app/output'))
    parser.add_argument('--private-dir', default=os.environ.get('PRIVATE_DIR'))
    parser.add_argument('--pilot-fold', choices=['CALTECH'])
    args = parser.parse_args(argv)
    output = None
    try:
        data, method, output, private = prepare_destinations(args.data_dir, args.method_contract,
                                                           args.output_dir, args.private_dir)
        result = run(data, method, output, private, args.pilot_fold)
        print(json.dumps(result, sort_keys=True, allow_nan=False), flush=True)
        return 0
    except Exception as error:
        if output is not None:
            failure_evidence(output, error)
        print(f'{type(error).__name__}: {error}', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
