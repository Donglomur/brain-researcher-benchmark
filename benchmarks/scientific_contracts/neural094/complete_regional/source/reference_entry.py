"""Fixed trusted reference capsule ABI, future isolated worker only.

Whole fit and regional composition are distinct. All estimators, preprocessing,
menus, fitted serialization and query inference call captured original sources.
Native guard/stack qualification is required by the outer selected authority;
this source does not execute or replace that qualification campaign.
"""
import io
from pathlib import Path
import sys


def _modules(public):
    # /runtime is an exact readonly trusted source inventory, never candidate
    # code. This path insertion occurs only inside the reference container.
    sys.path.insert(0, '/runtime')
    import regional_custody as custody
    import regional_sources as loader
    import subset_reference as subset
    cfg = public['payload']
    budget = custody.Budget(cfg['loader_read_bytes'], cfg['loader_write_bytes'], cfg['worker_seconds'])
    modules = loader.load_group('/runtime/numerics', cfg['numerical_sources'], budget, loader.NUMERICAL)
    # The captured codec tick uses its original module-global work deadline.
    # Bind the same clock established before source loading; no extra time.
    budget.tick()
    modules['worker'].WORK_END = budget.end
    import numpy as np
    import scipy
    import sklearn
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.exceptions import ConvergenceWarning
    versions = {'numpy': np.__version__, 'scipy': scipy.__version__, 'sklearn': sklearn.__version__}
    modules['reference'].stack_versions(versions)
    return custody, subset, budget, modules, np, versions, LogisticRegression, HistGradientBoostingClassifier, ConvergenceWarning


def _packet(root, public, c, budget, mods, np):
    phase = 'fitval' if public['phase'] == 'train' else 'query'
    body = c.read(root, 'MANIFEST.json', public['payload']['packet'], budget)
    manifest = c.parsed(body); mods['validator'].validate_manifest(manifest)
    c.need(manifest['phase'] == phase, 'Exact reference packet phase')
    members, arrays = {}, {}
    for name, descriptor in manifest['files'].items():
        raw = c.read(root, name, {k: descriptor[k] for k in ('bytes', 'sha256')}, budget)
        mods['worker'].archive_contract(raw, np)
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            arrays[name] = {k: archive[k] for k in archive.files}
        members[name] = raw
    return manifest, members, arrays


def train(public, tools):
    c, subset, budget, mods, np, versions, logistic, hgb, warning = _modules(public)
    manifest, members, arrays = _packet('/training', public, c, budget, mods, np)
    ref = mods['reference']; counters = {}
    kw = dict(versions=versions, np=np, ref=ref, choice=mods['choice'], validator=mods['validator'],
              worker=mods['worker'], LogisticRegression=logistic, HistGradientBoostingClassifier=hgb,
              ConvergenceWarning=warning, tick=budget.tick, counters=counters)
    if public['payload']['reference_kind'] == 'whole':
        bundle, report = ref.fit_references(arrays, manifest, public['payload']['reference_sha256'],
                **{k: v for k, v in kw.items() if k not in ('ref', 'worker')})
        raw = mods['worker'].serialize_trusted(bundle)
        restored = mods['worker'].deserialize_trusted(raw, c.pin(raw))
        c.need(set(restored['states']) == set(ref.REFERENCES), 'Original trusted serialization roundtrip')
        report = dict(report, empirical_fit_counters=counters, serialization_roundtrip_verified=True,
                      model_commitment_pending_external_closure=True)
    else:
        c.need(public['payload']['reference_kind'] == 'regional', 'Explicit whole or regional reference')
        transfers = public['payload']['whole_fit_transfer']
        bodies = {name: c.read('/training/whole_fit', name, descriptor, budget)
                  for name, descriptor in transfers.items()}
        whole = c.restore_whole_for_reference_worker(bodies)
        projected = {'members': members, 'manifest': manifest,
                     'selection_private': public['payload']['selection_private']}
        result = subset.fit_regional(projected, whole, custody=c, **kw)
        raw, report = result['model_bytes'], result['composition']
    c.write('/output', 'model.bin', raw, budget)
    c.write('/output', 'fit_report.json', c.encoded(report), budget)
    return {'fit_files': ['model.bin', 'fit_report.json']}


def predict(public, tools):
    c, subset, budget, mods, np, versions, logistic, hgb, warning = _modules(public)
    commitment = c.parsed(c.read('/fit', 'MODEL_COMMIT.json', public['payload']['commitment'], budget))
    raw = c.read('/fit', 'model.bin', {k: commitment['artifact'][k] for k in ('bytes', 'sha256')}, budget)
    # Model capture/commit is verified before opening query arrays.
    saved = mods['worker'].deserialize_trusted(raw, commitment['artifact'])
    manifest, members, arrays = _packet('/query', public, c, budget, mods, np)
    counters = {}
    kw = dict(versions=versions, np=np, choice=mods['choice'], validator=mods['validator'],
              ConvergenceWarning=warning, tick=budget.tick, counters=counters)
    if public['payload']['reference_kind'] == 'whole':
        result, report = mods['reference'].infer_references(saved, arrays, manifest, commitment, **kw)
    else:
        projected = {'members': members, 'manifest': manifest,
                     'selection_private': public['payload']['selection_private']}
        result, report = subset.infer_regional(raw, commitment, projected, ref=mods['reference'],
                                             worker=mods['worker'], **kw)
    c.need(counters.get('estimator_fit_attempts', 0) == 0 and report['query_fits'] == 0,
           'Original inference performs no new reference fit')
    c.write('/output', 'inference_report.json', c.encoded(report), budget)
    return [{'reference': name, 'rows': [{'token': token, 'probabilities': [float(v) for v in row]}
             for token, row in zip(manifest['case_tokens'], result[name], strict=True)]}
            for name in mods['reference'].REFERENCES]
