"""Pre-original cross-route numerical qualification; manufactured arrays only."""
from decimal import Decimal, localcontext
import math

import numpy as np
import pytest

import selection_kernel as public
import source_numerics as private


def decimal_mean(values):
    with localcontext() as context:
        context.prec = 200
        return float(sum((Decimal.from_float(float(x)) for x in values), Decimal(0))/Decimal(len(values)))


@pytest.mark.parametrize('scale', [1., 2.**-40])
@pytest.mark.parametrize('step,status', [(2.**-20, 'active'), (2.**-52, 'numerical_resolution'), (0., 'source_zero_variance')])
def test_independent_selected_mean_rounding_routes(scale, step, status):
    ids = [str(i+100) for i in range(40)]
    pairs = np.array([(i,j) for i in range(1,8) for j in range(i+1,8)])
    z = np.empty((40,3,len(pairs)))
    for i in range(40):
        first = (1.+np.arange(len(pairs))*2.**-8)*scale
        second = first+(.125+(-step if i%2==0 else step))*scale
        z[i] = [first, second, (first+second)/2]
    own = public.analyze(z,z,ids,pairs)
    independent_rows = []
    for i,sid in enumerate(ids):
        row = dict(subject_id=sid,n_edges=len(pairs))
        for scheme in public.SCHEMES:
            ix = own['evidence'][sid][scheme+'_edge_indices']
            first = decimal_mean(z[i,0,ix])
            second = decimal_mean(z[i,1,ix])
            row[scheme+'_delta'] = second-first
            if scheme == 'forward':
                row.update(forward_first_half=first,forward_second_half=second)
        independent_rows.append(row)
    replay = public.analyze(z,z,ids,pairs,accepted_rows=independent_rows)
    assert all(x['status']==status for x in replay['support_diagnostics'].values())
    for scheme in public.SCHEMES:
        assert replay['summaries']['selection_schemes'][scheme]['delta_mean'] == decimal_mean([r[scheme+'_delta'] for r in independent_rows])
    if status == 'active':
        # A one-ULP CSV serialization change remains compatible, but a uniform
        # offset that a centered-error-only guard would miss must fail.
        benign = [dict(r) for r in independent_rows]
        for row in benign:
            for scheme in public.SCHEMES:
                row[scheme+'_delta'] = float(np.nextafter(row[scheme+'_delta'], math.inf))
        public.analyze(z,z,ids,pairs,accepted_rows=benign)
        shifted = [dict(r) for r in independent_rows]
        for row in shifted: row['independent_delta'] += 2.**-24*scale
        with pytest.raises(public.ContractError, match='full-error'):
            public.analyze(z,z,ids,pairs,accepted_rows=shifted)


@pytest.mark.parametrize('frames', [12,13])
def test_independent_source_connectivity_routes(frames):
    rng = np.random.Generator(np.random.PCG64(196))
    raw = rng.normal(size=(4,frames,7))
    raw[:,:,6] = .1
    ref = private.reconstruct(raw)
    half = frames//2
    chunks = [raw[:,:half,:],raw[:,frames-half:,:],raw]
    sd = np.array([[[public.population_sd(chunks[s][p,:,r]) for r in range(7)] for s in range(3)] for p in range(4)])
    mask = (sd>1e-8).all(axis=(0,1))
    assert np.array_equal(mask,ref['common_roi_mask'])
    independently_computed = np.array([[public.fisher_z(chunks[s][p][:,mask]) for s in range(3)] for p in range(4)])
    np.testing.assert_allclose(independently_computed,ref['fisher_z'],atol=5e-14,rtol=0)
    for p in range(4):
        for s in range(3): public.edge_fidelity(independently_computed[p,s],ref['fisher_z'][p,s])
