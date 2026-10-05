"""Public numerical mechanics; synthetic fixtures are not source evidence.

Derived results come from accepted ROI means. Reference vectors serve only the
published fidelity condition, never a second hidden downstream numerical gate.
"""
from collections import Counter
from itertools import combinations
import math
import numpy as np

EPS = np.finfo(np.float64).eps
ARMS = ("all_frames", "censored")
ROI_STATUSES = ("ok", "insufficient_frames", "constant", "numerically_constant")
PAIR_STATUSES = ("ok", "insufficient_common_edges", "constant_edge_vector", "numerically_constant_edge_vector")
PIPELINE = "msc-six-person-censoring-sensitivity-v2"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def stable_l2(values):
    x = np.asarray(values, dtype=np.float64)
    require(np.isfinite(x).all(), "nonfinite norm input")
    if not x.size:
        return 0.0
    scale = float(np.max(np.abs(x)))
    result = 0.0 if scale == 0 else scale * math.sqrt(float(np.sum((x / scale) ** 2)))
    require(math.isfinite(result), "nonfinite L2 norm")
    return result


def vector_state(values):
    x = np.asarray(values, dtype=np.float64)
    require(x.ndim == 1 and np.isfinite(x).all(), "vector must be finite and one dimensional")
    n = len(x)
    result = dict(n_frames=n, raw_l2=None, centered_l2=None, zero_bound=None,
                  status="insufficient_frames", centered=np.zeros_like(x), unit=None)
    if n < 2:
        return result
    scale = float(np.max(np.abs(x)))
    exact_constant = bool(np.max(x) == np.min(x))
    if scale == 0:
        raw = centered = bound = 0.0
        c = np.zeros_like(x)
    elif exact_constant:
        raw, centered = math.sqrt(n), 0.0
        bound = 10 * n * EPS * raw
        c = np.zeros_like(x)
    else:
        u = x / scale
        c = u - np.mean(u, dtype=np.float64)
        raw = math.sqrt(float(np.sum(u * u)))
        centered = math.sqrt(float(np.sum(c * c)))
        bound = 10 * n * EPS * raw
    status = "constant" if exact_constant else "numerically_constant" if centered <= bound else "ok"
    result.update(raw_l2=scale * raw, centered_l2=scale * centered, zero_bound=scale * bound,
                  status=status, centered=scale * c, unit=c / centered if status == "ok" else None)
    require(all(math.isfinite(result[k]) for k in ("raw_l2", "centered_l2", "zero_bound")),
            "nonfinite vector diagnostic")
    require(np.isfinite(result["centered"]).all(), "nonfinite centered vector")
    return result


def validate_fidelity(submitted, reference, source_peak, masks):
    x, ref, peak = np.asarray(submitted), np.asarray(reference), np.asarray(source_peak)
    require(x.shape == ref.shape and x.ndim == 3, "ROI mean shape")
    require(peak.shape == (x.shape[0], x.shape[2]), "source peak shape")
    require(np.isfinite(x).all() and np.isfinite(ref).all(), "nonfinite ROI means")
    require(np.isfinite(peak).all() and (peak >= 0).all(), "source peak domain")
    tolerance = 1e-10 * peak[:, None, :] + 1e-9 * np.abs(ref)
    require(np.all(np.abs(x - ref) <= tolerance), "ROI means do not match original source")
    require(np.asarray(masks).shape == x.shape[:2], "mask shape")
    for run in range(x.shape[0]):
        for arm in ARMS:
            keep = np.ones(x.shape[1], dtype=bool) if arm == "all_frames" else masks[run].astype(bool)
            for roi in range(x.shape[2]):
                a, b = x[run, keep, roi], ref[run, keep, roi]
                if len(b) < 2:
                    continue
                if np.max(b) == np.min(b):
                    require(np.max(a) == np.min(a), "source constant ROI gained temporal variation")
                    continue
                sa, sb = vector_state(a), vector_state(b)
                if sa["status"] != "ok" and sb["status"] != "ok":
                    continue
                error = stable_l2(sa["centered"] - sb["centered"])
                require(error <= 1e-6 * stable_l2(sb["centered"]),
                        "ROI centered-signal fidelity exceeds public relative bound")


def coefficient(value):
    value = float(value)
    require(math.isfinite(value) and abs(value) <= 1 + 1e-12, "Pearson coefficient outside numerical domain")
    return float(np.clip(value, -1, 1))


def pearson(a, b):
    require(a["status"] == b["status"] == "ok", "Pearson requires two supported vectors")
    return coefficient(np.dot(a["unit"], b["unit"]))


def pair_state(a, b):
    require(a["n_frames"] == b["n_frames"], "pair support differs")
    status = "ok"
    if a["n_frames"] < 2:
        status = "insufficient_common_edges"
    elif "constant" in (a["status"], b["status"]):
        status = "constant_edge_vector"
    elif "numerically_constant" in (a["status"], b["status"]):
        status = "numerically_constant_edge_vector"
    row = {f"{field}_{suffix}": state[field] for suffix, state in (("a", a), ("b", b))
           for field in ("raw_l2", "centered_l2", "zero_bound")}
    row.update(status=status, pair_r=pearson(a, b) if status == "ok" else None)
    return row


def group(values):
    defined = [float(v) for v in values if v is not None]
    status = "empty_qc_subset" if not values else "incomplete_subjects" if len(defined) != len(values) else "ok"
    return dict(value=float(np.mean(defined)) if status == "ok" else None,
                status=status, n_expected=len(values), n_defined=len(defined))


def derive(primitives):
    """Every arm/FC/summary is fresh. Tiny dimensions are fixture-only;
    the production reference loader enforces all18 runs/818 frames/264 ROIs.
    """
    x = np.asarray(primitives["roi_means"], dtype=np.float64)
    masks = np.asarray(primitives["tmask"], dtype=bool)
    subjects, sessions = list(primitives["run_subject"]), list(primitives["run_session"])
    roi_ids = list(map(int, primitives["roi_ids"]))
    runs, frames, rois = x.shape
    require(masks.shape == (runs, frames) and len(subjects) == len(sessions) == runs, "primitive axes")
    require(len(roi_ids) == rois and len(set(zip(subjects, sessions))) == runs, "duplicate axes")
    states = []
    for run in range(runs):
        states.append([[vector_state(x[run, np.ones(frames, bool) if arm == "all_frames" else masks[run], roi])
                        for roi in range(rois)] for arm in ARMS])
    common = np.array([all(states[r][a][j]["status"] == "ok" for r in range(runs) for a in range(2))
                       for j in range(rois)], dtype=bool)
    edges = np.array(list(combinations(roi_ids, 2)), dtype=np.int64).reshape(-1, 2)
    index = {v: j for j, v in enumerate(roi_ids)}
    valid = np.array([common[index[a]] and common[index[b]] for a, b in edges], dtype=bool)
    n_edges = len(edges)
    rvals = np.full((runs, 2, n_edges), np.nan)
    for run in range(runs):
        for arm in range(2):
            chosen = np.flatnonzero(common)
            if not len(chosen):
                continue
            normalized = np.stack([states[run][arm][j]["unit"] for j in chosen])
            matrix = normalized @ normalized.T
            require(np.isfinite(matrix).all() and np.max(np.abs(matrix)) <= 1 + 1e-12,
                    "nonfinite/out-of-domain recomputed FC")
            lookup = {roi_ids[j]: k for k, j in enumerate(chosen)}
            chosen_edges = edges[valid]
            left = np.array([lookup[a] for a in chosen_edges[:, 0]], dtype=int)
            right = np.array([lookup[b] for b in chosen_edges[:, 1]], dtype=int)
            rvals[run, arm, valid] = np.clip(matrix[left, right], -1, 1)
    zvals = np.arctanh(np.clip(rvals, -.999, .999))
    roi_rows, session_rows = [], []
    for run in range(runs):
        nr = int(masks[run].sum())
        session_rows.append(dict(subject_id=subjects[run], session_id=sessions[run], n_frames=frames,
                                 n_retained=nr, n_excluded=frames-nr, header_tr_seconds=1.0,
                                 analysis_tr_seconds=2.2, tr_policy="explicit_acquisition_frame_interval_override",
                                 retained_seconds=nr*11/5, retained_minutes=nr*11/300,
                                 duration_qc_pass=11*nr >= 3000))
        for arm_i, arm in enumerate(ARMS):
            for j, roi in enumerate(roi_ids):
                row = dict(subject_id=subjects[run], session_id=sessions[run], arm=arm, roi_id=roi,
                           common_roi=bool(common[j]))
                row.update({k: states[run][arm_i][j][k] for k in
                            ("n_frames", "raw_l2", "centered_l2", "zero_bound", "status")})
                roi_rows.append(row)
    pair_rows, reliability_rows = [], []
    for subject in sorted(set(subjects)):
        indices = sorted([i for i, s in enumerate(subjects) if s == subject], key=lambda i: sessions[i])
        for arm_i, arm in enumerate(ARMS):
            for i, j in combinations(indices, 2):
                a, b = vector_state(zvals[i, arm_i, valid]), vector_state(zvals[j, arm_i, valid])
                row = dict(subject_id=subject, arm=arm, session_a=sessions[i], session_b=sessions[j],
                           n_candidate_edges=n_edges, n_common_edges=int(valid.sum()))
                row.update(pair_state(a, b))
                pair_rows.append(row)
        retained = [int(masks[i].sum()) for i in indices]
        expected = len(indices)*(len(indices)-1)//2
        row = dict(subject_id=subject, n_sessions=len(indices), n_frames_total=len(indices)*frames,
                   n_frames_retained=sum(retained), minimum_retained_seconds=min(retained)*11/5,
                   minimum_retained_minutes=min(retained)*11/300,
                   qc_pass=all(11*n >= 3000 for n in retained), n_pairs_expected=expected)
        for arm in ARMS:
            values = [p["pair_r"] for p in pair_rows if p["subject_id"] == subject and p["arm"] == arm]
            defined = [v for v in values if v is not None]
            row[f"{arm}_n_pairs_defined"] = len(defined)
            row[f"reliability_{arm}"] = float(np.mean(defined)) if len(defined) == expected and expected else None
            row[f"{arm}_status"] = "ok" if len(defined) == expected and expected else "incomplete_pairs"
        reliability_rows.append(row)
    included = [r["subject_id"] for r in reliability_rows if r["qc_pass"]]
    groups = {}
    for arm in ARMS:
        groups[f"all_six_{arm}"] = group([r[f"reliability_{arm}"] for r in reliability_rows])
        groups[f"conditional_qc_{arm}"] = group([r[f"reliability_{arm}"] for r in reliability_rows if r["qc_pass"]])
    stats = dict(status="ok", pipeline_id=PIPELINE, n_subjects=len(reliability_rows),
                 n_sessions_per_subject=len(set(sessions)), n_runs=runs, n_rois=rois,
                 n_candidate_edges=n_edges, n_common_rois=int(common.sum()), n_common_edges=int(valid.sum()),
                 n_frames_total=runs*frames, n_frames_retained=int(masks.sum()), qc_included_subject_ids=included,
                 qc_excluded_subject_ids=[r["subject_id"] for r in reliability_rows if not r["qc_pass"]],
                 group_mean_reliability=groups, roi_status_counts=dict(Counter(r["status"] for r in roi_rows)),
                 pair_status_counts=dict(Counter(r["status"] for r in pair_rows)),
                 fisher_clip_counts={arm: int(np.sum(np.abs(rvals[:, a, valid]) > .999)) for a, arm in enumerate(ARMS)})
    return dict(session_qc=session_rows, roi_status=roi_rows, session_pairs=pair_rows,
                reliability=reliability_rows, stats=stats, common_roi=common,
                edge_roi_ids=edges, edge_valid=valid, raw_r=rvals, fisher_z=zvals)
