"""Operator reference source for the current helper-free A/B packets.

Mechanical packaging of the existing developer control and exact helper bodies;
not an independent model, executed result or newly qualified inference method.
This file is outside both candidate packets and has not been run on authentic data.
"""
import argparse
import contextlib
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys

SEED_OFFSET = 0



# Exact existing helper implementations, packaged into this operator program.
"""Explicit Bambi0.9.1 Student-t model; imported only in isolated qualification."""
import math


def source_scales(x, y):
    import numpy as np
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.ndim != 1 or x.shape != y.shape or len(x) < 5 or not np.isfinite([x, y]).all():
        raise ValueError("finite equal one-dimensional arrays required")
    xm, ym, sx, sy = float(x.mean()), float(y.mean()), float(x.std()), float(y.std())
    if sx <= 0 or sy <= 0:
        raise ValueError("nonconstant source arrays required")
    b = 2.5 * sy / sx
    a = math.sqrt((2.5 * sy) ** 2 + (xm * b) ** 2)
    return {"x_mean": xm, "y_mean": ym, "x_sd": sx, "y_sd": sy, "beta_sd": b, "alpha_c_sd": a}


def build(x, y):
    import numpy as np
    import pymc as pm
    s = source_scales(x, y)
    with pm.Model() as model:
        alpha_c = pm.Normal("alpha_c", mu=s["y_mean"], sigma=s["alpha_c_sd"])
        beta = pm.Normal("beta", mu=0, sigma=s["beta_sd"])
        sigma = pm.HalfStudentT("sigma", nu=4, sigma=s["y_sd"])
        nu = pm.Gamma("nu", alpha=2, beta=0.1)
        pm.Deterministic("alpha", alpha_c - s["x_mean"] * beta)
        mu = alpha_c + beta * (np.asarray(x) - s["x_mean"])
        pm.StudentT("observed", nu=nu, mu=mu, sigma=sigma, observed=np.asarray(y))
    return model, s


def independent_log_density(x, y, alpha_c, beta, sigma, nu):
    """Independent scalar density: no PyMC, NumPy or source_scales call."""
    n = len(x)
    xm, ym = math.fsum(x) / n, math.fsum(y) / n
    sx = math.sqrt(math.fsum((v - xm) ** 2 for v in x) / n)
    sy = math.sqrt(math.fsum((v - ym) ** 2 for v in y) / n)
    b = 2.5 * sy / sx
    a = math.sqrt((2.5 * sy) ** 2 + (xm * b) ** 2)

    def normal(v, m, sd):
        return -.5 * math.log(2 * math.pi) - math.log(sd) - .5 * ((v - m) / sd) ** 2

    def student(v, df, loc, scale):
        return (math.lgamma((df + 1) / 2) - math.lgamma(df / 2)
            - .5 * math.log(df * math.pi) - math.log(scale)
            - (df + 1) / 2 * math.log1p(((v - loc) / scale) ** 2 / df))

    if sigma <= 0 or nu <= 0:
        return -math.inf
    likelihood = math.fsum(student(v, nu, alpha_c + beta * (u - xm), sigma) for u, v in zip(x, y))
    gamma = 2 * math.log(.1) - math.lgamma(2) + math.log(nu) - .1 * nu
    return likelihood + normal(alpha_c, ym, a) + normal(beta, 0, b) + math.log(2) + student(sigma, 4, 0, sy) + gamma

"""Independent scalar saved-draw summaries; no inference or third-party imports."""
import math


def summarize(chains):
    if len(chains) < 2 or any(len(row) < 200 or len(row) % 100 for row in chains):
        raise ValueError("at least two complete equal 100-draw batches per chain")
    lengths = {len(row) for row in chains}
    if len(lengths) != 1:
        raise ValueError("equal chain lengths")
    values = [float(value) for chain in chains for value in chain]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("finite draws")
    n = len(values)
    mean = math.fsum(values) / n
    sd = math.sqrt(math.fsum((v - mean)**2 for v in values) / n)
    ordered = sorted(values)
    step = int(math.floor(.94 * n))
    index = min(range(n - step), key=lambda i: ordered[i + step] - ordered[i])
    batches = [math.fsum(chain[start:start + 100]) / 100
               for chain in chains for start in range(0, len(chain), 100)]
    batch_mean = math.fsum(batches) / len(batches)
    mcse = math.sqrt(math.fsum((v - batch_mean)**2 for v in batches) / (len(batches) * (len(batches) - 1)))
    return {"mean": mean, "sd_population": sd, "hdi_94_low": ordered[index],
            "hdi_94_high": ordered[index + step], "mcse_mean_batch": mcse}



def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.input))
    from bootstrap import setup
    setup(a.input)
    import numpy as np
    import pymc as pm
    import arviz as az
    contract = json.loads((a.input / 'MODEL_CONTRACT.json').read_text())
    raw = (a.input / 'meg_slope_data_sbg.csv').read_bytes()
    if len(raw) != contract['input']['bytes'] or hashlib.sha256(raw).hexdigest() != contract['input']['sha256']:
        raise ValueError('Original complete public CSV')
    reader = csv.DictReader(io.StringIO(raw.decode('utf8')))
    if reader.fieldnames != contract['columns']:
        raise ValueError('Exact source CSV schema')
    rows = list(reader)
    ids = [r['subject_id'] for r in rows]
    if (len(rows) != 655 or len(set(ids)) != 655 or
        hashlib.sha256(json.dumps(ids, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            != contract['participant_id_hash']):
        raise ValueError('All655 original participants, no filtering')
    columns = {k: np.asarray([float(r[k]) for r in rows], dtype=np.float64) for k in contract['columns'][2:]}
    if any(not np.isfinite(v).all() or v.std(ddof=0) <= 0 for v in columns.values()):
        raise ValueError('Finite nonconstant complete columns')
    standardized = {k: (v-v.mean())/v.std(ddof=0) for k, v in columns.items()}
    variables = ['alpha_c', 'beta', 'sigma', 'nu', 'alpha']
    result = {'schema_version': 1, 'input_sha256': hashlib.sha256(raw).hexdigest(),
              'target': 'salzburg_bambi091_six_student_t_targets', 'models': {}}
    shapes, progress_rows = [], []
    for spec in contract['models']:
        table = columns if spec['scale'] == 'raw' else standardized
        x, y = table['age'], table[spec['condition']]
        model, scales = build(x, y)
        # Independent scalar density checks preserve centered-prior and Jacobian semantics.
        density = model.compile_logp(jacobian=False)
        density_j = model.compile_logp(jacobian=True)
        for ac, beta, sigma, nu in [(scales['y_mean'], -.01, scales['y_sd'], 6.),
                                    (scales['y_mean']+.12, .08, scales['y_sd']*1.8, 2.3),
                                    (scales['y_mean']-.05, -.13, scales['y_sd']*.7, 18.)]:
            point = {'alpha_c': ac, 'beta': beta, 'sigma_log__': math.log(sigma), 'nu_log__': math.log(nu)}
            exact = independent_log_density(x.tolist(), y.tolist(), ac, beta, sigma, nu)
            checks = [float(density(point))-exact,
                      float(density_j(point))-exact-math.log(sigma)-math.log(nu)]
            if not all(math.isfinite(v) and abs(v) <= 1e-8 for v in checks):
                raise ValueError('Independent source density/Jacobian check')
        progress = {str(c): {'tune': 0, 'draws': 0, 'last': -1} for c in range(4)}
        def callback(trace, draw):
            q = progress[str(draw.chain)]
            if draw.draw_idx != q['last']+1:
                raise ValueError('Sequential full chain')
            q['last'] = int(draw.draw_idx)
            q['tune' if draw.tuning else 'draws'] += 1
        with model:
            idata = pm.sample(draws=2000, tune=2000, chains=4, cores=2,
                random_seed=spec['seed']+SEED_OFFSET, target_accept=.9,
                progressbar=False, return_inferencedata=True, callback=callback,
                compute_convergence_checks=True, idata_kwargs={'log_likelihood': False})
        if any(q['tune'] != 2000 or q['draws'] != 2000 for q in progress.values()):
            raise ValueError('Every prescribed chain/draw/tune count')
        arrays = {k: np.asarray(idata.posterior[k].values, dtype=np.float64) for k in variables}
        if any(v.shape != (4, 2000) or not np.isfinite(v).all() for v in arrays.values()):
            raise ValueError('Every finite full posterior')
        summary = {k: summarize(v.tolist()) for k, v in arrays.items()}
        diag = {'chains': 4, 'draws_per_chain': 2000, 'tune_per_chain': 2000,
                'divergences': int(idata.sample_stats['diverging'].sum()),
                'max_rhat': float(az.rhat(idata, var_names=variables, method='rank').to_array().max(skipna=False)),
                'min_ess_bulk': float(az.ess(idata, var_names=variables, method='bulk').to_array().min(skipna=False)),
                'min_ess_tail': float(az.ess(idata, var_names=variables, method='tail').to_array().min(skipna=False))}
        for k in ('max_rhat', 'min_ess_bulk', 'min_ess_tail'):
            if not math.isfinite(diag[k]):
                diag[k] = None
        # Retain every model even if its diagnostics are poor or unavailable.
        result['models'][spec['name']] = {'summary': summary, 'diagnostics': diag}
        shapes.extend([list(v.shape) for v in arrays.values()])
        progress_rows.append({'name': spec['name'], 'seed': spec['seed']+SEED_OFFSET, 'chains': progress})
    body = (json.dumps(result, allow_nan=False, separators=(',', ':'))+'\n').encode()
    if len(body) > 200000 or list(a.out.iterdir()):
        raise ValueError('One fresh bounded summary')
    with (a.out/'summary.json').open('xb') as f:
        f.write(body); f.flush(); os.fsync(f.fileno())
    return {'status': 'six_full_source_models_completed', 'models': list(result['models']),
            'participants': 655, 'candidate_fits': 6, 'chains': 4,
            'tune_per_chain': 2000, 'draws_per_chain': 2000, 'seed_offset': SEED_OFFSET,
            'posterior_shapes': shapes, 'progress': progress_rows, 'new_reference_fits': 0,
            'draws_retained_in_candidate_scratch_only': True,
            'diagnostics_self_reported_not_verified_by_unchanged_summary_grader': True}


if __name__ == '__main__':
    with contextlib.redirect_stdout(sys.stderr):
        report = main()
    print(json.dumps(report, allow_nan=False), flush=True)
