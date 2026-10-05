"""Private original-source bank. Historical scalar/correlation banks fail closed."""
import hashlib
import json
import numpy as np
import connectivity_contract as q

BUILDER_ID = 'original-cnp-surface-source-v2'
METHOD_SHA256 = '7378a0ccd4663907e2e8df3db724ba9caa3e21ee80b955ea637863db1769a23c'
SOURCE_MANIFEST_SHA256 = 'f4ea1c9f5a3a75d722fedd2cece082dd84502f20c5c7d2d11704c5bcc45594e3'


def load_reference(path):
    with np.load(path, allow_pickle=False) as archive:
        required = {'ref_'+k for k in q.ARRAY_FIELDS} | {'reference_json'}
        q.require(required <= set(archive.files), 'Obsolete/incomplete source bank')
        q.require(archive['reference_json'].shape == () and archive['reference_json'].dtype.kind == 'U',
                  'Primitive bank metadata required')
        payload = json.loads(str(archive['reference_json']))
        ref = {k: np.array(archive['ref_'+k]) for k in q.ARRAY_FIELDS}
    q.require(isinstance(payload, dict) and {'provenance', 'metadata', 'cohort_rows',
              'parcel_rows', 'edge_rows', 'connectivity_rows', 'method_contract_json',
              'source_manifest_json'} <= set(payload), 'Missing bank provenance')
    provenance = payload['provenance']
    q.require(provenance.get('builder_id') == BUILDER_ID and provenance.get('status') == 'complete',
              'Bank is not a complete original-source computation')
    q.require(provenance.get('method_contract_sha256') == METHOD_SHA256 and
              provenance.get('source_manifest_sha256') == SOURCE_MANIFEST_SHA256,
              'Untrusted source/method bank identity')
    ref.update(payload)
    validate_reference(ref)
    ref['derived'] = q.summarize(ref)
    return ref


def validate_reference(ref):
    """Check complete identity/algebra; does not pretend this re-reads raw data."""
    meta = ref['metadata']; method = meta['method_contract']
    q.require(hashlib.sha256(ref['method_contract_json'].encode()).hexdigest() == METHOD_SHA256 and
              hashlib.sha256(ref['source_manifest_json'].encode()).hexdigest() == SOURCE_MANIFEST_SHA256,
              'Bank original contract bytes are untrusted')
    q.match(method, json.loads(ref['method_contract_json']), 'bank public method', 'exact', closed=True)
    original_manifest = json.loads(ref['source_manifest_json'])
    q.match(meta['source_sha256'], {r['path']: r['sha256'] for r in original_manifest['files']},
            'bank source map', 'exact', closed=True)
    q.require(meta['status'] == 'complete' and meta['task_id'] == 'CLINCONN-001', 'Incomplete bank metadata')
    q.require(meta['method_contract_sha256'] == METHOD_SHA256 and
              meta['source_manifest_sha256'] == SOURCE_MANIFEST_SHA256, 'Mismatched bank fingerprints')
    q.require(isinstance(meta['source_sha256'], dict) and meta['source_sha256'] and
              all(isinstance(k, str) and isinstance(v, str) and len(v) == 64 and
                  set(v) <= set('0123456789abcdef') for k, v in meta['source_sha256'].items()),
              'Invalid bank source hashes')
    subjects = ref['subject_id']; parcels = ref['parcel_id']; edges = ref['edge_id']
    for axis in (subjects, parcels):
        q.require(axis.dtype.kind == 'U' and axis.ndim == 1 and len(set(axis.tolist())) == len(axis),
                  'Invalid source string axis')
    q.require(subjects.tolist() == sorted(subjects.tolist()), 'Noncanonical bank participant order')
    cohort = q.keyed(ref['cohort_rows'], ['subject_id'])
    q.require(len(cohort) == method['cohort']['n_candidates'] and len(subjects) == method['cohort']['n_selected'],
              'Incomplete original cohort bank')
    selected = sorted(r['subject_id'] for r in cohort.values() if r['selected'])
    q.require(selected == subjects.tolist(), 'Cohort/array membership mismatch')
    unavailable = sorted(r['subject_id'] for r in cohort.values() if not r['selected'])
    q.require(unavailable == sorted(method['cohort']['unavailable_released_derivatives']), 'Unapproved source exclusion')
    prows = q.keyed(ref['parcel_rows'], ['parcel_id'])
    included = [r for r in prows.values() if r['included']]
    included.sort(key=lambda r: (r['hemisphere'], r['annotation_index']))
    q.require([r['parcel_id'] for r in included] == parcels.tolist(), 'Wrong canonical atlas axis')
    n, p = len(subjects), len(parcels)
    ii, jj = np.triu_indices(p, 1); e = len(ii)
    q.require(edges.dtype.kind in 'iu' and np.array_equal(edges, np.arange(e)), 'Wrong full candidate edge axis')
    erows = sorted(ref['edge_rows'], key=lambda r: r['edge_id'])
    q.require(len(erows) == e, 'Incomplete candidate edge catalogue')
    centers = np.array([[r['centroid_'+v] for v in 'xyz'] for r in included], float)
    for index, row in enumerate(erows):
        q.require(row['edge_id'] == index and row['parcel_i'] == parcels[ii[index]] and
                  row['parcel_j'] == parcels[jj[index]], 'Wrong edge endpoints')
        q.close(row['distance'], float(np.linalg.norm(centers[ii[index]]-centers[jj[index]])),
                'geometry', 'bank geometry')
    for name in q.ARRAY_FIELDS[3:]:
        expected = (n, p) if name.startswith('parcel_') else (n, e)
        q.require(ref[name].shape == expected, 'Wrong bank source matrix shape')
    status = ref['parcel_status']
    q.require(status.dtype.kind == 'U' and np.isin(status, ['ok', 'constant_input', 'numerical_zero_residual']).all(),
              'Unknown bank parcel status')
    for name in ('parcel_original_centered_l2', 'parcel_residual_l2', 'parcel_zero_bound'):
        x = ref[name]
        q.require(x.dtype.kind == 'f' and np.isfinite(x).all() and (x >= 0).all(), 'Invalid bank norm')
    crows = q.keyed(ref['connectivity_rows'], ['subject_id'])
    q.require(set(crows) == {(s,) for s in subjects}, 'Incomplete source subject audit')
    for index, sid in enumerate(subjects):
        row = crows[(sid,)]
        q.require(row['group'] == cohort[(sid,)]['group'], 'Wrong source diagnosis')
        q.require(row['n_frames'] > 33 and row['n_fd_defined'] == row['n_frames']-(not row['first_fd_defined']),
                  'Wrong FD support denominator')
        q.require(row['n_confound_columns'] == 13 and 0 <= row['nuisance_rank'] <= 13, 'Wrong nuisance support')
        q.close(row['nuisance_rank_threshold'], 100*q.EPS, 'floor', 'nuisance rank threshold')
        q.close(row['mean_fd'], row['fd_sum']/row['n_fd_defined'], 'source', 'FD arithmetic')
        q.require(row['mean_fd'] >= 0 and row['qc_fd_lt_0_2'] == (row['mean_fd'] < .2), 'Wrong source QC category')
        bound = 10*max(row['n_frames'], 13)*q.EPS*np.maximum(ref['parcel_original_centered_l2'][index], q.TINY)
        q.array_close(ref['parcel_zero_bound'][index], bound, 'floor', 'source normalization bound')
    expected_valid = (status[:, ii] == 'ok') & (status[:, jj] == 'ok')
    q.require(ref['edge_valid'].dtype.kind == 'b' and np.array_equal(ref['edge_valid'], expected_valid),
              'Bank validity does not follow source parcels')
    valid = ref['edge_valid']
    for name in ('raw_r', 'fisher_z'):
        q.require(ref[name].dtype.kind == 'f' and np.array_equal(np.isnan(ref[name]), ~valid)
                  and np.isfinite(ref[name][valid]).all() and not np.isinf(ref[name]).any(),
                  'Wrong bank undefined pattern')
    q.require(np.all(np.abs(ref['raw_r'][valid]) <= 1+1e-12), 'Invalid bank Pearson coefficient')
    q.require(ref['fisher_clipped'].dtype.kind == 'b' and
              np.array_equal(ref['fisher_clipped'], valid & (np.abs(ref['raw_r']) > .999)), 'Wrong bank Fisher clipping flags')
    transformed = np.arctanh(np.clip(ref['raw_r'][valid], -.999, .999))
    q.require(np.allclose(ref['fisher_z'][valid], transformed, atol=1e-12, rtol=1e-12), 'Bank Fisher transform is inconsistent')
