"""Manufactured-source mechanics only; never opens original ABIDE arrays."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import warnings

import numpy as np
import pytest
from sklearn.covariance import ledoit_wolf
from sklearn.preprocessing import StandardScaler

TASK = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('oracle_under_test', TASK / 'solution/compute.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
METHOD = json.loads((TASK / 'environment/method_contract.json').read_text())


def example():
    rng = np.random.RandomState(41)
    x = rng.normal(size=(40, 6))
    y = np.arange(40) % 2
    sites = np.asarray(['CALTECH'] * 10 + ['SITEB'] * 15 + ['SITEC'] * 15)
    return x, y, sites


def toy_selected():
    x, y, sites = example()
    rows = [dict(phenotype_row=i, subject_id=100 + i, file_id=f'sub_{i}', site=sites[i],
        eye_code=1 if y[i] else 2, label=int(y[i]), source_path=f'roi/{i}', source_sha256='a' * 64,
        n_timepoints=100, n_rois=4, n_constant_rois=0, n_low_sd_rois=0,
        included=True, exclusion_reason='included', selected_index=i) for i in range(len(y))]
    return rows, x


@pytest.mark.parametrize('value,expected', [('123', 123), ('123.0', 123), ('1e2', 100), ('-3', -3)])
def test_original_integral_fields(value, expected):
    assert c.strict_integer(value) == expected


@pytest.mark.parametrize('value', ['1.00000000000000001', 'NaN', 'Infinity', 'x', ''])
def test_fractional_or_nonfinite_integer_rejected(value):
    with pytest.raises(Exception):
        c.strict_integer(value)


def test_standardization_population_scale_and_preserved_constants():
    data = np.column_stack([np.arange(12.), np.ones(12) * 0.1, np.ones(12) * 9])
    z, exact, low = c.standardized_source(data)
    assert exact == low == 2
    np.testing.assert_allclose(z[:, 0].std(ddof=0), 1)
    assert np.ptp(z[:, 1]) == 0 and np.ptp(z[:, 2]) == 0


@pytest.mark.parametrize('bad', [np.zeros(3), np.ones((1, 3)), np.ones((10, 1)), np.full((3, 3), np.nan)])
def test_bad_source_arrays_fail(bad):
    with pytest.raises(ValueError):
        c.standardized_source(bad)


def test_covariance_all_constant_fails_no_zero_imputation():
    with pytest.raises(ValueError, match='covariance'):
        c.connectivity(np.full((80, 4), 0.1))


def test_lw_matches_explicit_formula_and_lower_triangle():
    raw = np.random.RandomState(9).normal(size=(80, 5))
    raw[:, 3] = 0.1
    feature, shrink, constant, low = c.connectivity(raw)
    z, _, _ = c.standardized_source(raw)
    q = z - z.mean(axis=0)
    sample = q.T @ q / len(q)
    mu = np.trace(sample) / 5
    delta = np.sum((sample - mu * np.eye(5)) ** 2) / 5
    beta = min((np.sum(np.sum(q*q, axis=1)**2) / len(q) - np.sum(sample**2)) / (5*len(q)), delta)
    ratio = 0 if beta == 0 else beta / delta
    cov = (1-ratio)*sample + ratio*mu*np.eye(5)
    expected = cov / np.sqrt(np.outer(np.diag(cov), np.diag(cov)))
    np.testing.assert_allclose(shrink, ratio, atol=1e-14)
    np.testing.assert_allclose(feature, expected[np.tril_indices(5, -1)], atol=1e-14)
    assert constant == low == 1


def test_split_complete_site_blocked_and_canonical_complements():
    x, y, sites = example()
    plan = c.split_plan(y, sites)
    assert [p[2] for p in plan[:3]] == ['CALTECH', 'SITEB', 'SITEC']
    for scheme in ('loso', 'random10'):
        tests = []
        for name, _, site, train, test in plan:
            if name != scheme:
                continue
            assert np.all(np.diff(train) > 0)
            assert set(train).isdisjoint(test)
            assert set(train) | set(test) == set(range(len(y)))
            if scheme == 'loso':
                assert set(sites[test]) == {site} and site not in sites[train]
            tests.extend(test)
        assert sorted(tests) == list(range(len(y)))


@pytest.mark.parametrize('y,sites', [(np.zeros(20, int), ['A']*20),
    (np.array([0]*9+[1]*11), ['A']*10+['B']*10),
    (np.array([0]*10+[1]*10), ['A']*10+['B']*10)])
def test_impossible_split_fails(y, sites):
    with pytest.raises(ValueError):
        c.split_plan(y, sites)


@pytest.mark.parametrize('truth,pred,ba,opened,closed', [([0,0],[0,1],.5,None,.5),
    ([1,1],[1,1],1,1,None), ([0,1],[1,0],0,0,0), ([],[],None,None,None)])
def test_confusion_supported_class_mean(truth, pred, ba, opened, closed):
    actual = c.confusion(truth, pred)
    assert (actual['balanced_accuracy'], actual['open_recall'], actual['closed_recall']) == (ba, opened, closed)


def test_stable_certificate_equals_independent_duality_gap():
    x, y, _ = example()
    theta = np.random.RandomState(7).normal(size=7) * .03
    a = np.column_stack([x, np.ones(len(x))])
    t = 2*y - 1
    alpha = 2*np.maximum(0, 1-t*(a@theta))
    p, gap, limit = c.certificate(x, y, theta[:-1], theta[-1])
    dual = alpha.sum() - .5*np.sum((a.T@(t*alpha))**2) - .25*np.sum(alpha**2)
    np.testing.assert_allclose(p-dual, gap, rtol=1e-13)
    assert limit == 1e-6*(1+p)


def test_fitted_toy_certificate_and_train_only_scaler(tmp_path):
    x, y, sites = example()
    split = c.split_plan(y, sites)[0]
    model, row, decision, prediction, captured = c.fit_fold(x, y, split, tmp_path)
    train, test = split[-2:]
    expected = StandardScaler().fit(x[train])
    np.testing.assert_array_equal(model['scaler_mean'], expected.mean_)
    np.testing.assert_array_equal(model['scaler_variance'], expected.var_)
    np.testing.assert_allclose(decision, expected.transform(x[test]) @ model['coefficient'] + model['intercept'])
    np.testing.assert_array_equal(prediction, decision > 0)
    assert row['certificate_gap'] <= row['certificate_limit'] and not captured
    assert (tmp_path / 'fold_loso_00.npz').is_file()


def test_failed_certificate_preserves_candidate_checkpoint(tmp_path, monkeypatch):
    x, y, sites = example()
    monkeypatch.setattr(c, 'certificate', lambda *a: (1., 9., .000002))
    with pytest.raises(ValueError, match='certificate failed'):
        c.fit_fold(x, y, c.split_plan(y, sites)[0], tmp_path)
    with np.load(tmp_path / 'fold_loso_00.npz', allow_pickle=False) as arrays:
        assert json.loads(arrays['diagnostics_json'].item())['certificate_gap'] == 9


def test_convergence_warning_preserved_before_failure(tmp_path, monkeypatch):
    native = c.bvls_dual
    def warning_fit(*a, **kw):
        result = native(*a, **kw)
        warnings.warn('manufactured warning', RuntimeWarning)
        return result
    monkeypatch.setattr(c, 'bvls_dual', warning_fit)
    x, y, sites = example()
    with pytest.warns(RuntimeWarning), pytest.raises(ValueError, match='convergence failure'):
        c.fit_fold(x, y, c.split_plan(y, sites)[0], tmp_path)
    with np.load(tmp_path / 'fold_loso_00.npz') as arrays:
        assert json.loads(arrays['diagnostics_json'].item())['warnings'][0]['message'] == 'manufactured warning'


@pytest.mark.parametrize('kind', ['equal', 'nested', 'ancestor', 'traversal', 'private_source', 'private_output'])
def test_source_output_overlap_refused(tmp_path, kind):
    source = tmp_path / 'source'; source.mkdir()
    output, private = tmp_path / 'output', None
    if kind == 'equal': output = source
    if kind == 'nested': output = source / 'child'
    if kind == 'ancestor': output = tmp_path
    if kind == 'traversal': output = tmp_path / 'fake' / '..' / 'source'
    if kind == 'private_source': private = source / 'private'
    if kind == 'private_output': private = output / 'private'
    with pytest.raises(ValueError):
        c.prepare_destinations(source, tmp_path / 'method', output, private)


def test_symlink_ancestor_refused(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    link = tmp_path / 'link'; link.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError, match='Symlink'):
        c.prepare_destinations(link / 'missing', tmp_path / 'method', tmp_path / 'out')


def test_existing_evidence_preserved(tmp_path):
    output = tmp_path / 'output'; output.mkdir()
    sentinel = output / 'findings.md'; sentinel.write_text('preserve')
    assert c.main(['--data-dir', str(tmp_path/'source'), '--method-contract', str(tmp_path/'method'),
                   '--output-dir', str(output)]) == 1
    assert sentinel.read_text() == 'preserve' and list(output.iterdir()) == [sentinel]


def test_source_failure_three_artifacts_and_reason(tmp_path):
    output = tmp_path / 'output'
    assert c.main(['--data-dir', str(tmp_path/'source'), '--method-contract', str(tmp_path/'method'),
                   '--output-dir', str(output)]) == 1
    assert {p.name for p in output.iterdir()} == {'eye_decoding_results.json','run_metadata.json','findings.md','failure_report.json'}
    for file in ('eye_decoding_results.json','run_metadata.json'):
        value = json.loads((output/file).read_text())
        assert value['status'] == 'failed_precondition' and value['reason']


def test_actual_shell_entrypoint_failure(tmp_path):
    result = subprocess.run([str(TASK/'solution/solve.sh'), '--data-dir', str(tmp_path/'source'),
        '--method-contract', str(tmp_path/'missing'), '--output-dir', str(tmp_path/'output')], capture_output=True)
    assert result.returncode == 1
    assert json.loads((tmp_path/'output/eye_decoding_results.json').read_text())['status'] == 'failed_precondition'


@pytest.mark.parametrize('pilot', [False, True])
def test_manufactured_full_eight_artifacts_and_pilot_scope(tmp_path, monkeypatch, pilot):
    selected, x = toy_selected()
    method = json.loads(json.dumps(METHOD)); method['features']['n_rois'] = 4
    manifest = {'files': [dict(path='fake', sha256='a'*64)]}
    monkeypatch.setattr(c, 'load_inputs', lambda *a: (method, manifest))
    monkeypatch.setattr(c, 'read_source', lambda *a: (selected, selected, x, np.zeros(len(x))))
    output, private = tmp_path/'output', tmp_path/'private'
    args = ['--data-dir', str(tmp_path/'source'), '--method-contract', str(tmp_path/'method'),
            '--output-dir', str(output), '--private-dir', str(private)]
    if pilot: args += ['--pilot-fold', 'CALTECH']
    assert c.main(args) == 0
    assert {p.name for p in output.iterdir()} == set(METHOD['artifacts'])
    result = json.loads((output/'eye_decoding_results.json').read_text())
    assert result['status'] == ('resource_pilot' if pilot else 'ok')
    if pilot:
        assert result['cv_balanced_accuracy'] is None and result['random_kfold_balanced_accuracy'] is None
        assert result['schemes']['loso']['n_folds'] == 1 and result['schemes']['random10']['n_folds'] == 0
    else:
        assert result['schemes']['loso']['n_folds'] == 3 and result['schemes']['random10']['n_folds'] == 10
    with np.load(output/'fold_models.npz', allow_pickle=False) as arrays:
        assert arrays['coefficient'].shape == (1 if pilot else 13, 6)
    metadata = json.loads((output/'run_metadata.json').read_text())
    assert metadata['source_observed']['n_selected'] == 40


def test_checkpoint_write_failure_never_complete_status(tmp_path, monkeypatch):
    selected, x = toy_selected()
    method = json.loads(json.dumps(METHOD)); method['features']['n_rois'] = 4
    monkeypatch.setattr(c, 'load_inputs', lambda *a: (method, {'files': []}))
    monkeypatch.setattr(c, 'read_source', lambda *a: (selected, selected, x, np.zeros(len(x))))
    native = c.write_npz
    def fail(path, **arrays):
        if Path(path).name.startswith('fold_loso'): raise OSError('manufactured private disk failure')
        native(path, **arrays)
    monkeypatch.setattr(c, 'write_npz', fail)
    assert c.main(['--data-dir', str(tmp_path/'source'), '--method-contract', str(tmp_path/'method'),
        '--output-dir', str(tmp_path/'output'), '--private-dir', str(tmp_path/'private'), '--pilot-fold', 'CALTECH']) == 1
    result = json.loads((tmp_path/'output/eye_decoding_results.json').read_text())
    assert result['status'] == 'failed_precondition' and 'disk failure' in result['reason']


@pytest.mark.parametrize('harbor', [False, True])
def test_local_and_harbor_stager_layout(tmp_path, monkeypatch, harbor):
    method = tmp_path/'method.json'
    method.write_text(json.dumps(dict(method_id=c.METHOD_ID, source=dict(manifest_sha256=c.SOURCE_SHA256))))
    monkeypatch.setattr(c, 'METHOD_SHA256', hashlib.sha256(method.read_bytes()).hexdigest())
    environment = tmp_path/'environment'; environment.mkdir()
    helper = environment/'stage_source.py'
    helper.write_text(f'MANIFEST_SHA256={c.SOURCE_SHA256!r}\ndef verify_staged(path): return {{"test": "offline"}}\n')
    monkeypatch.setattr(c, '__file__', str(tmp_path/('other/solution' if harbor else 'solution')/'compute.py'))
    native = c.regular
    def regular(path):
        return helper if str(path) == '/opt/source/stage_source.py' else native(path)
    monkeypatch.setattr(c, 'regular', regular)
    assert c.load_inputs(tmp_path/'source', method)[1] == {'test': 'offline'}


def test_source_parser_original_row_identity_and_unavailable(tmp_path, monkeypatch):
    columns = ['SUB_ID','FILE_ID','SITE_ID','EYE_STATUS_AT_SCAN']
    with (tmp_path/'phenotype.csv').open('w') as stream:
        writer = csv.writer(stream); writer.writerow(columns)
        writer.writerows([[33,'C_0000033','C',2],[11,'no_filename','C',1],[22,'B_0000022','B',1]])
    header = '\t'.join('#'+str(i) for i in range(1,201))
    values = np.random.RandomState(17).normal(size=(78,200))
    for name in ('C','B'):
        with (tmp_path/(name+'.1D')).open('w') as stream:
            stream.write(header+'\n'); np.savetxt(stream,values)
    manifest = dict(files=[dict(role='phenotype',path='phenotype.csv'),
        *[dict(role='roi_timeseries',path=site+'.1D',phenotype_row_index=row,subject_id=str(subject),
               file_id=f'{site}_{subject:07d}',sha256='a'*64) for site,row,subject in [('C',0,33),('B',2,22)]]])
    method = json.loads(json.dumps(METHOD))
    method['source'].update(phenotype_rows=3,known_named_derivatives=2,known_no_filename_rows=1)
    ledger, selected, features, shrinkage = c.read_source(tmp_path,manifest,method)
    assert [r['subject_id'] for r in selected] == [33,22]
    assert [r['phenotype_row'] for r in selected] == [0,2]
    assert ledger[1]['source_path'] is None and ledger[1]['selected_index'] is None
    assert features.shape == (2,19900) and len(shrinkage)==2


def test_import_has_no_source_or_output_side_effects(tmp_path):
    result = subprocess.run([sys.executable, '-c',
        'import runpy; runpy.run_path('+repr(str(TASK/'solution/compute.py'))+', run_name="no_main")'],
        cwd=tmp_path, capture_output=True)
    assert result.returncode == 0 and not list(tmp_path.iterdir())


@pytest.mark.parametrize('failure', ['fit', 'certificate', 'nonfinite', 'shape', 'iteration_cap', 'status', 'success'])
def test_exception_and_iteration_checkpoint(tmp_path, monkeypatch, failure):
    native = c.bvls_dual
    def failing_fit(*a, **kw):
        if failure == 'fit':
            warnings.warn('warning before fit exception', RuntimeWarning)
            raise RuntimeError('fit aborted')
        result = native(*a, **kw)
        if failure == 'nonfinite': result.x[0] = np.nan
        if failure == 'shape': result.x = result.x[:-1]
        if failure == 'iteration_cap': result.nit = 30000
        if failure == 'status': result.status = 0
        if failure == 'success': result.success = False
        return result
    monkeypatch.setattr(c, 'bvls_dual', failing_fit)
    if failure == 'certificate':
        def fail(*a): raise ValueError('certificate arithmetic exception')
        monkeypatch.setattr(c, 'certificate', fail)
    x, y, sites = example()
    with warnings.catch_warnings(record=True), pytest.raises((ValueError, RuntimeError)):
        c.fit_fold(x, y, c.split_plan(y, sites)[0], tmp_path)
    with np.load(tmp_path/'fold_loso_00.npz', allow_pickle=False) as arrays:
        assert arrays['scaler_mean'].shape == (6,) and len(arrays['train_indices']) == 30
        diagnostic = json.loads(arrays['diagnostics_json'].item())
        if failure == 'fit':
            assert diagnostic['stage'] == 'dual_factorization_or_solver' and diagnostic['warnings'][0]['message']
            assert 'coefficient' not in arrays
        elif failure == 'iteration_cap': assert diagnostic['n_iter'] == 30000
        elif failure == 'status': assert diagnostic['solver_status'] == 0
        elif failure == 'success': assert diagnostic['solver_success'] is False
        elif failure in ('nonfinite','shape'):
            assert diagnostic['status']=='failed_precondition' and 'raw_dual_alpha' in arrays
            assert 'coefficient' not in arrays
        else: assert diagnostic['status'] == 'failed_precondition' and 'coefficient' in arrays


def test_bvls_call_exact_frozen_transformation_and_settings(monkeypatch):
    x, y, sites = example()
    native = c.lsq_linear
    def inspect(b, d, **kwargs):
        expected = (x@x.T+1)*(2*y-1)[:,None]*(2*y-1)[None,:]+.5*np.eye(len(y))
        np.testing.assert_allclose(b.T@b, expected, atol=2e-14)
        np.testing.assert_allclose(b.T@d, np.ones(len(y)), atol=1e-14)
        assert kwargs == dict(bounds=(0,np.inf),method='bvls',tol=1e-12,max_iter=30000,lsq_solver='exact')
        return native(b, d, **kwargs)
    monkeypatch.setattr(c, 'lsq_linear', inspect)
    result = c.bvls_dual(x, y)
    assert result.success and result.status > 0 and result.nit < 30000


@pytest.mark.parametrize('n,p,scale', [(40,7,1.), (24,70,1.), (50,9,100.), (32,12,.001)])
def test_bvls_distinct_nnls_and_exact_primal_gap(n, p, scale):
    from scipy.optimize import nnls
    rng = np.random.RandomState(3)
    z = rng.normal(size=(n,p))*scale
    y = np.arange(n)%2; signed = 2*y-1
    result = c.bvls_dual(z,y)
    hessian = (z@z.T+1)*signed[:,None]*signed[None,:]+.5*np.eye(n)
    lower = np.linalg.cholesky(hessian)
    expected, _ = nnls(lower.T,np.linalg.solve(lower,np.ones(n)),maxiter=30000)
    np.testing.assert_allclose(result.x,expected,atol=1e-9,rtol=1e-8)
    w, b = z.T@(signed*result.x), np.sum(signed*result.x)
    primal, gap, limit = c.certificate(z,y,w,b)
    assert result.success and np.all(result.x>=0) and gap<=limit


def test_bvls_matches_small_primal_svm_not_logistic_or_unpenalized_intercept():
    from sklearn.svm import LinearSVC
    z,y,_ = example()
    fitted = c.bvls_dual(z,y)
    signed = 2*y-1
    candidate = np.r_[z.T@(signed*fitted.x), np.sum(signed*fitted.x)]
    other = LinearSVC(C=1,loss='squared_hinge',penalty='l2',dual=False,tol=1e-12,max_iter=30000,
                      fit_intercept=True,intercept_scaling=1,random_state=0).fit(z,y)
    np.testing.assert_allclose(candidate,np.r_[other.coef_[0],other.intercept_[0]],atol=1e-7,rtol=1e-6)


def test_factorization_exception_preserves_scaler_no_fallback(tmp_path, monkeypatch):
    def bad_cholesky(*a, **kw): raise np.linalg.LinAlgError('manufactured factorization error')
    monkeypatch.setattr(c,'cholesky',bad_cholesky)
    x,y,sites = example()
    with pytest.raises(np.linalg.LinAlgError):
        c.fit_fold(x,y,c.split_plan(y,sites)[0],tmp_path)
    with np.load(tmp_path/'fold_loso_00.npz') as arrays:
        diagnostic=json.loads(arrays['diagnostics_json'].item())
        assert 'factorization error' in diagnostic['reason']
        assert 'dual_alpha' not in arrays and 'coefficient' not in arrays


def test_projected_roundoff_preserves_raw_and_passes_real_certificate(tmp_path, monkeypatch):
    native = c.bvls_dual
    retained = {}
    def roundoff_return(z,y):
        result = native(z,y)
        bound = np.flatnonzero(result.x == 0)
        assert len(bound)>0, 'Manufactured case must have a genuinely active bound'
        result.x[bound[0]] = -1e-22
        retained['raw'] = result.x.copy()
        return result
    monkeypatch.setattr(c,'bvls_dual',roundoff_return)
    x = np.random.RandomState(3).normal(size=(40,7))
    y = np.arange(40)%2
    split=('loso',0,'manufactured',np.arange(40),np.arange(2))
    model,row,_,_,_ = c.fit_fold(x,y,split,tmp_path)
    assert row['certificate_gap'] <= row['certificate_limit']
    with np.load(tmp_path/'fold_loso_00.npz') as arrays:
        np.testing.assert_array_equal(arrays['raw_dual_alpha'],retained['raw'])
        np.testing.assert_array_equal(arrays['dual_alpha'],np.maximum(retained['raw'],0))
        np.testing.assert_array_equal(arrays['dual_projection_delta'],arrays['dual_alpha']-retained['raw'])
        diagnostic=json.loads(arrays['diagnostics_json'].item())
        assert diagnostic['n_raw_negative']==1 and diagnostic['max_projection_change']==1e-22


def test_large_bad_negative_projection_still_fails_unchanged_certificate(tmp_path, monkeypatch):
    native = c.bvls_dual
    def bad_candidate(*a):
        result=native(*a)
        result.x[:]=-1000
        return result
    monkeypatch.setattr(c,'bvls_dual',bad_candidate)
    x,y,sites=example()
    with pytest.raises(ValueError,match='Public objective certificate failed'):
        c.fit_fold(x,y,c.split_plan(y,sites)[0],tmp_path)
    with np.load(tmp_path/'fold_loso_00.npz') as arrays:
        assert np.all(arrays['raw_dual_alpha']==-1000) and np.all(arrays['dual_alpha']==0)
        diagnostic=json.loads(arrays['diagnostics_json'].item())
        assert diagnostic['max_projection_change']==1000
        assert diagnostic['certificate_gap']>diagnostic['certificate_limit']


def test_no_private_cli_retains_dual_vectors_axes_and_certificate(tmp_path, monkeypatch):
    selected,x=toy_selected()
    method=json.loads(json.dumps(METHOD)); method['features']['n_rois']=4
    monkeypatch.setattr(c,'load_inputs',lambda *a:(method,{'files':[]}))
    monkeypatch.setattr(c,'read_source',lambda *a:(selected,selected,x,np.zeros(len(x))))
    native=c.bvls_dual
    observed={}
    def retain(z,y):
        fitted=native(z,y)
        observed['raw']=fitted.x.copy()
        return fitted
    monkeypatch.setattr(c,'bvls_dual',retain)
    output=tmp_path/'output'
    assert c.main(['--data-dir',str(tmp_path/'source'),'--method-contract',str(tmp_path/'method'),
                   '--output-dir',str(output),'--pilot-fold','CALTECH'])==0
    assert {p.name for p in output.iterdir()}==set(METHOD['artifacts'])
    assert not (tmp_path/'private').exists()
    with np.load(output/'fold_models.npz',allow_pickle=False) as arrays:
        mask=arrays['oracle_dual_training_mask'][0]
        assert mask.dtype.kind=='b'
        np.testing.assert_array_equal(mask,np.arange(40)>=10)
        np.testing.assert_array_equal(arrays['oracle_dual_phenotype_row'],np.arange(40))
        np.testing.assert_array_equal(arrays['oracle_dual_subject_id'],np.arange(100,140))
        raw=arrays['oracle_raw_dual_alpha_by_selected_index'][0]
        projected=arrays['oracle_projected_dual_alpha_by_selected_index'][0]
        np.testing.assert_array_equal(raw[mask],observed['raw'])
        np.testing.assert_array_equal(projected[mask],np.maximum(observed['raw'],0))
        assert np.all(raw[~mask]==0) and np.all(projected[~mask]==0)
        y=np.asarray([r['label'] for r in selected])
        z=(x[mask]-arrays['scaler_mean'][0])/arrays['scaler_scale'][0]
        w=z.T@((2*y[mask]-1)*projected[mask]); b=np.sum((2*y[mask]-1)*projected[mask])
        np.testing.assert_allclose(arrays['coefficient'][0],w,atol=0,rtol=0)
        assert arrays['intercept'][0]==b
        primal,gap,limit=c.certificate(z,y[mask],w,b)
        assert gap<=limit
    metadata=json.loads((output/'run_metadata.json').read_text())
    assert 'padding' in metadata['reference_diagnostics']


def test_late_failure_receipt_preserves_existing_complete_marker(tmp_path):
    original = dict(status='ok', retained='earlier marker')
    c.write_json(tmp_path/'run_metadata.json', original)
    c.failure_evidence(tmp_path, OSError('late disk failure'))
    assert json.loads((tmp_path/'run_metadata.json').read_text()) == original
    failed = json.loads((tmp_path/'failure_report.json').read_text())
    assert failed['status'] == 'failed_precondition' and 'late disk failure' in failed['reason']


def test_private_completion_only_after_all_public_files(tmp_path, monkeypatch):
    selected, x = toy_selected()
    method = json.loads(json.dumps(METHOD)); method['features']['n_rois'] = 4
    monkeypatch.setattr(c, 'load_inputs', lambda *a: (method, {'files': []}))
    monkeypatch.setattr(c, 'read_source', lambda *a: (selected, selected, x, np.zeros(len(x))))
    native = c.write_json
    def checked(path, value):
        if Path(path).name == 'completion.json':
            assert {p.name for p in (tmp_path/'output').iterdir()} == set(METHOD['artifacts'])
            raise OSError('late completion error')
        return native(path, value)
    monkeypatch.setattr(c, 'write_json', checked)
    assert c.main(['--data-dir', str(tmp_path/'source'), '--method-contract', str(tmp_path/'method'),
        '--output-dir', str(tmp_path/'output'), '--private-dir', str(tmp_path/'private'), '--pilot-fold', 'CALTECH']) == 1
    assert not (tmp_path/'private/completion.json').exists()
    assert json.loads((tmp_path/'output/failure_report.json').read_text())['status'] == 'failed_precondition'
