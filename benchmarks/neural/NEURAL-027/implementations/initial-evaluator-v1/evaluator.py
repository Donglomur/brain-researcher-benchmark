"""NEURAL-027 source-frame packet construction and prospective reference evaluation.

Original implementation; no author code is vendored. See implementation.json and task docs.
Only operator-side data preparation/scoring receives source stimulus identities.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import time

import numpy as np

AREA_IDS = ((8,), (0, 1, 2, 9), (5, 6), (3, 4))
AREA_NAMES = ("V1", "mHV", "lHV", "aHV")
SOURCE_FIELDS = ("ft_WallID", "ft_trInd", "ft_move", "ft_Pos", "ft_CorrSpc")
HOLDS = [
    "Authentic complete selected payloads, source alignment, stimulus identities and animal population unverified.",
    "Area pooling is a prospective calibration, not verified cell registration or source-equivalent prediction.",
    "Cohort, phase interpretation, position grid, access and resource protocol require prospective scientific admission.",
    "No authentic reference, independent scientific replication, competence threshold or protected test evaluated.",
    "Source/data rights and safe conversion of trusted author object NPY payloads require operator verification.",
    "Public data remain development-only; no causal, intervention or exact-millisecond inference is supported.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value, name, ndim=None):
    a = np.asarray(value, dtype=float)
    require(ndim is None or a.ndim == ndim, f"{name}: wrong dimensions")
    require(np.isfinite(a).all(), f"{name}: nonfinite values")
    return a


def integer_ids(value, name):
    a = finite(value, name, 1)
    require(np.equal(a, np.floor(a)).all(), f"{name}: noninteger IDs")
    return a.astype(np.int64)


def unique_strings(value, name):
    require(isinstance(value, list) and value and all(isinstance(x, str) and x for x in value), f"{name}: nonempty strings required")
    require(len(set(value)) == len(value), f"{name}: duplicate values")
    return value


def checked_classes(value):
    classes = integer_ids(value, "classes")
    require(len(classes) >= 2 and len(set(classes)) == len(classes), "at least two unique classes required")
    require(np.array_equal(classes, np.sort(classes)) and np.isin(classes, np.arange(7)).all(), "classes must be sorted source stim_id values 0..6")
    return classes


def wall_identity(value):
    # Source wall identities can be names; never coerce names into canonical IDs.
    if isinstance(value, (bytes, np.bytes_)):
        value = value.decode("utf-8")
    if isinstance(value, (str, np.str_)):
        require(bool(value.strip()), "empty source wall identity")
        return str(value)
    require(isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, (bool, np.bool_)), "invalid source wall identity type")
    require(np.isfinite(value) and value == np.floor(value), "nonfinite or fractional source wall identity")
    return int(value)


def validate_plan(plan):
    require(plan.get("schema_version") == 1, "plan schema_version must be 1")
    classes = checked_classes(plan["classes"])
    edges = finite(plan["position_edges"], "position_edges", 1)
    require(len(edges) >= 2 and np.all(np.diff(edges) > 0) and edges[0] >= 0 and edges[-1] <= 1, "position edges must strictly increase within [0,1]")
    train_mice = unique_strings(plan["train_mice"], "train_mice")
    eval_mice = unique_strings(plan["evaluation_mice"], "evaluation_mice")
    require(not set(train_mice) & set(eval_mice), "animal train/evaluation leakage")
    train_phases = unique_strings(plan["train_phases"], "train_phases")
    eval_phases = unique_strings(plan["evaluation_phases"], "evaluation_phases")
    require(not set(train_phases) & set(eval_phases), "training and evaluation phases overlap")
    require(plan.get("calibration") == "source_anatomical_area_mean_v1", "explicit anatomical calibration required")
    require(plan.get("pre_reward_training_attestation") is True, "operator must attest training phases precede reward learning")
    require(isinstance(plan.get("phase_semantics"), dict) and set(plan["phase_semantics"]) == set(train_phases + eval_phases), "document semantics for every phase")
    require(all(isinstance(s, str) and s.strip() for s in plan["phase_semantics"].values()), "phase semantics cannot be blank")
    sessions = plan["sessions"]
    require(isinstance(sessions, list) and sessions, "complete selected session manifest required")
    seen, observed_train, observed_eval, observed_phases = set(), set(), set(), set()
    for s in sessions:
        require(set(s) == {"session_id", "mname", "datexp", "blk", "phase"}, "unexpected/missing manifest session fields")
        require(all(isinstance(v, str) and v for v in s.values()), "session identities must be nonempty strings")
        sid = "_".join(s[k] for k in ("mname", "datexp", "blk"))
        require(s["session_id"] == sid and sid not in seen, "session ID mismatch or duplicate")
        seen.add(sid)
        if s["mname"] in train_mice:
            require(s["phase"] in train_phases, "training animal has non-training phase")
            observed_train.add(s["mname"])
        else:
            require(s["mname"] in eval_mice and s["phase"] in eval_phases, "session outside evaluation cohort/phases")
            observed_eval.add(s["mname"])
            observed_phases.add(s["phase"])
    require(observed_train == set(train_mice) and observed_eval == set(eval_mice), "declared animal absent from session manifest")
    require(observed_phases == set(eval_phases), "declared evaluation phase absent")
    return classes, edges


def construct_session(session, plan):
    """Build complete trial x fixed-position packets from decoded author fields.

    ``spks`` is the source list of neuron x frame chunks, or its concatenated array.
    ``ft_Pos`` and ``Corridor_Length`` must have identical source units, verified by
    the operator. All bins use only frames of their trial. No interpolation occurs.
    """
    classes, edges = validate_plan(plan)
    meta = {k: session[k] for k in ("session_id", "mname", "datexp", "blk", "phase")}
    require(meta in plan["sessions"], "unplanned or mismatched session")
    raw = session["spks"]
    if isinstance(raw, (list, tuple)):
        require(len(raw) > 0, "empty source spks list")
        chunks = [finite(c, "spks chunk", 2) for c in raw]
        require(len({a.shape[1] for a in chunks}) == 1, "source chunks have unequal frame counts")
        spks = np.concatenate(chunks, axis=0)
    else:
        spks = finite(raw, "spks", 2)
    nneu, nfr = spks.shape
    require(nneu > 0 and nfr > 0, "empty neural array")
    iarea = integer_ids(session["iarea"], "iarea")
    require(len(iarea) == nneu, "neuron area alignment mismatch")
    regional = []
    for name, ids in zip(AREA_NAMES, AREA_IDS):
        mask = np.isin(iarea, ids)
        require(mask.any(), f"missing cortical region {name}")
        regional.append(spks[mask].mean(axis=0))
    regional = np.stack(regional, axis=1)
    beh = session["behavior"]
    vectors, tails = {}, {}
    for key in SOURCE_FIELDS:
        a = np.asarray(beh[key]) if key == "ft_WallID" else np.asarray(beh[key], dtype=float)
        require(a.ndim == 1 and len(a) >= nfr, f"{key}: behavior shorter than neural frames or not vector")
        tails[key] = len(a) - nfr
        vectors[key] = a[:nfr]
    trials = vectors["ft_trInd"]
    require(not np.isinf(trials).any(), "infinite trial identity")
    # Source documents NaN outside behavior. These frames must not be selected.
    corridor = vectors["ft_CorrSpc"]
    movement = vectors["ft_move"]
    require(np.isfinite(corridor).all() and np.isin(corridor, [0, 1]).all(), "corridor flags must be finite binary")
    require(np.isfinite(movement).all(), "movement must be finite")
    selected = (corridor == 1) & (movement > 0)
    require(np.isfinite(trials[selected]).all(), "selected frames have missing trial identity")
    valid_trials = trials[np.isfinite(trials)]
    require(valid_trials.size and np.equal(valid_trials, np.floor(valid_trials)).all(), "invalid trial identities")
    require((valid_trials >= 0).all(), "negative trial identity")
    # Reused/non-contiguous trial IDs can silently fuse different trials.
    sequence = trials[np.isfinite(trials)].astype(int)
    runs = sequence[np.r_[True, sequence[1:] != sequence[:-1]]]
    require(len(runs) == len(set(runs.tolist())), "trial ID recurs after another trial")
    length = float(beh["Corridor_Length"])
    require(np.isfinite(length) and length > 0, "invalid Corridor_Length")
    positions = vectors["ft_Pos"] / length
    require(np.isfinite(positions[selected]).all(), "selected positions are nonfinite")
    require(((positions[selected] >= 0) & (positions[selected] <= 1)).all(), "selected ft_Pos/Corridor_Length outside [0,1]; verify source units")
    walls = vectors["ft_WallID"]
    raw_wall_ids = np.asarray(beh["UniqWalls"])
    require(raw_wall_ids.ndim == 1, "UniqWalls: wrong dimensions")
    wall_ids = [wall_identity(x) for x in raw_wall_ids]
    stim_ids = integer_ids(beh["stim_id"], "stim_id")
    require(len(wall_ids) == len(stim_ids) and len(wall_ids) == len(set(wall_ids)) and len(stim_ids) == len(set(stim_ids)), "ambiguous stimulus mapping")
    require(np.isin(stim_ids, np.arange(7)).all(), "source stim_id outside 0..6")
    wall_to_stim = dict(zip(wall_ids, stim_ids.tolist()))
    records, exclusions = [], []
    for tid in sorted(set(valid_trials.astype(int).tolist())):
        mask = selected & (trials == tid)
        if not mask.any():
            exclusions.append({"trial_id": tid, "reason": "no_moving_corridor_frames"})
            continue
        trial_walls = list(set(wall_identity(x) for x in walls[mask]))
        require(len(trial_walls) == 1 and trial_walls[0] in wall_to_stim, "trial has inconsistent or unmapped stimulus identity")
        label = wall_to_stim[trial_walls[0]]
        if label not in classes:
            exclusions.append({"trial_id": tid, "reason": "outside_predeclared_stimulus_set"})
            continue
        bins = []
        for b, (left, right) in enumerate(zip(edges[:-1], edges[1:])):
            in_bin = mask & (positions >= left) & ((positions <= right) if b == len(edges)-2 else (positions < right))
            if not in_bin.any():
                bins = []
                break
            # Stable opaque IDs contain no WallID, stim_id, phase or response label.
            iid = hashlib.sha256(f"{meta['session_id']}\0{tid}\0{b}".encode()).hexdigest()
            bins.append({"item_id": iid, "mname": meta["mname"], "phase": meta["phase"], "session_id": meta["session_id"],
                         "trial_id": tid, "position_bin": b, "label": int(label), "frame_count": int(in_bin.sum()),
                         "neural": regional[in_bin].mean(axis=0).tolist(),
                         "context": [float(movement[in_bin].mean()), float(positions[in_bin].mean())]})
        if bins:
            records.extend(bins)
        else:
            exclusions.append({"trial_id": tid, "reason": "incomplete_fixed_position_grid"})
    require(records, "session has no complete eligible trial packets")
    return records, {"session_id": meta["session_id"], "neural_frames": nfr, "neurons": nneu,
                     "area_counts": {n: int(np.isin(iarea, ids).sum()) for n, ids in zip(AREA_NAMES, AREA_IDS)},
                     "neurons_outside_declared_regions": int((~np.isin(iarea, sum(AREA_IDS, ()))).sum()),
                     "behavior_tail_frames": tails, "selected_frames": int(selected.sum()),
                     "discarded_unassigned_trial_frames": int(np.isnan(trials).sum()),
                     "retained_trials": len(records) // (len(edges)-1), "retained_frames": sum(r["frame_count"] for r in records),
                     "selected_frames_outside_position_grid": int((selected & ((positions < edges[0]) | (positions > edges[-1]))).sum()),
                     "exclusions": exclusions}


def prepare(sessions, plan):
    validate_plan(plan)
    require(len(sessions) == len(plan["sessions"]), "session population coverage mismatch")
    require(len({s["session_id"] for s in sessions}) == len(sessions), "duplicate input session")
    require({s["session_id"] for s in sessions} == {s["session_id"] for s in plan["sessions"]}, "missing or unexpected source sessions")
    train, evaluation, audit = [], [], []
    for session in sessions:
        records, summary = construct_session(session, plan)
        (train if session["mname"] in plan["train_mice"] else evaluation).extend(records)
        audit.append(summary)
    validate_records(train, plan["classes"])
    validate_records(evaluation, plan["classes"])
    return train, evaluation, audit


def validate_records(records, classes):
    require(records and len({r["item_id"] for r in records}) == len(records), "empty or duplicate item IDs")
    for r in records:
        require(isinstance(r["item_id"], str) and r["item_id"], "item identity missing")
        require(r["label"] in classes, "unknown target class")
    groups = {(r["mname"], r["phase"]) for r in records}
    for mouse, phase in groups:
        subset = [r for r in records if (r["mname"], r["phase"]) == (mouse, phase)]
        require({r["label"] for r in subset} == set(classes), f"unequal stimulus availability for {mouse}/{phase}")


def query(records):
    """Strict allowlist: no labels, animal/phase/source metadata or source WallID."""
    return [{"item_id": r["item_id"], "neural": list(r["neural"]), "context": list(r["context"])} for r in records]


class Reference:
    """Frozen train-only, mouse/class-balanced diagonal-Gaussian reference."""
    def __init__(self, classes, modality):
        require(modality in ("neural", "context"), "invalid feature modality")
        self.classes = checked_classes(classes)
        self.modality = modality

    def fit(self, train):
        validate_records(train, self.classes.tolist())
        x = finite([r[self.modality] for r in train], "training features", 2)
        require(x.shape[1] == (4 if self.modality == "neural" else 2), "unexpected feature width")
        y = np.array([r["label"] for r in train])
        mice = np.array([r["mname"] for r in train])
        # Each training animal and each class contribute equal total fitting mass.
        w = np.zeros(len(train))
        for mouse in np.unique(mice):
            for cls in self.classes:
                mask = (mice == mouse) & (y == cls)
                require(mask.any(), "training mouse lacks class")
                w[mask] = 1 / (len(np.unique(mice)) * len(self.classes) * mask.sum())
        self.mean = np.sum(x * w[:, None], axis=0)
        self.scale = np.sqrt(np.sum((x-self.mean)**2 * w[:, None], axis=0))
        self.scale[self.scale < 1e-12] = 1.0
        z = (x-self.mean) / self.scale
        self.centroids = np.stack([np.average(z[y == c], weights=w[y == c], axis=0) for c in self.classes])
        indices = np.array([np.flatnonzero(self.classes == c)[0] for c in y])
        self.variance = np.maximum(np.sum((z-self.centroids[indices])**2 * w[:, None], axis=0), 0.1)
        return self

    def predict(self, public_query):
        require(hasattr(self, "centroids"), "reference must be fitted")
        require(all(set(r) == {"item_id", "neural", "context"} for r in public_query), "query contains non-allowlisted fields")
        x = finite([r[self.modality] for r in public_query], "query features", 2)
        require(x.shape[1] == len(self.mean), "query feature width mismatch")
        z = (x-self.mean) / self.scale
        logits = -0.5 * (((z[:, None, :] - self.centroids[None, :, :])**2) / self.variance).sum(axis=2)
        logits -= logits.max(axis=1, keepdims=True)
        probs = np.exp(logits)
        probs /= probs.sum(axis=1, keepdims=True)
        return [{"item_id": r["item_id"], "probabilities": p.tolist()} for r, p in zip(public_query, probs)]


def score(expected, predictions, classes):
    classes = checked_classes(classes).tolist()
    validate_records(expected, classes)
    require(isinstance(predictions, list), "predictions must be a list")
    require(all(set(p) == {"item_id", "probabilities"} for p in predictions), "prediction fields mismatch")
    ids = [p["item_id"] for p in predictions]
    require(all(isinstance(i, str) for i in ids) and len(set(ids)) == len(ids), "duplicate or malformed prediction IDs")
    require(set(ids) == {r["item_id"] for r in expected}, "prediction coverage mismatch")
    lookup = {p["item_id"]: p["probabilities"] for p in predictions}
    p = finite([lookup[r["item_id"]] for r in expected], "probabilities", 2)
    require(p.shape == (len(expected), len(classes)), "probability shape mismatch")
    require((p >= 0).all() and (p <= 1).all() and np.allclose(p.sum(axis=1), 1, rtol=0, atol=1e-8), "invalid probability simplex")
    y = np.array([classes.index(r["label"]) for r in expected])
    ll = -np.log(np.clip(p[np.arange(len(y)), y], 1e-15, 1))
    correct = p.argmax(axis=1) == y
    by_phase = {}
    for phase in sorted({r["phase"] for r in expected}):
        per_mouse = {}
        for mouse in sorted({r["mname"] for r in expected if r["phase"] == phase}):
            mask = np.array([r["phase"] == phase and r["mname"] == mouse for r in expected])
            ba = np.mean([correct[mask & (y == c)].mean() for c in range(len(classes))])
            binding = sorted([[r["item_id"], int(r["label"])] for r in expected if r["phase"] == phase and r["mname"] == mouse])
            per_mouse[mouse] = {"log_loss": float(ll[mask].mean()), "balanced_accuracy": float(ba), "n_packets": int(mask.sum()),
                                "class_packet_counts": {str(c): int((mask & (y == i)).sum()) for i, c in enumerate(classes)},
                                "constant_probability_output": bool(np.allclose(p[mask], p[mask][0], rtol=0, atol=1e-12)),
                                "expected_binding_sha256": hashlib.sha256(json.dumps(binding, separators=(",", ":")).encode()).hexdigest()}
        by_phase[phase] = {"mouse_macro_log_loss": float(np.mean([v["log_loss"] for v in per_mouse.values()])),
                           "mouse_macro_balanced_accuracy": float(np.mean([v["balanced_accuracy"] for v in per_mouse.values()])),
                           "n_mice": len(per_mouse), "per_mouse": per_mouse}
    return {"classes_in_probability_order": classes, "by_phase": by_phase, "diagnostics": {"constant_probability_output": bool(np.allclose(p, p[0], rtol=0, atol=1e-12)),
                                                  "zero_target_probability_count": int((p[np.arange(len(y)), y] == 0).sum())}}


def compare(reference_scores, control_scores, draws=2000, seed=27):
    """Paired resampling of biological units; never resample position packets."""
    require(isinstance(draws, int) and draws >= 100, "at least 100 bootstrap draws required")
    rng = np.random.default_rng(seed)
    require(reference_scores["classes_in_probability_order"] == control_scores["classes_in_probability_order"], "class ordering mismatch")
    output = {}
    require(set(reference_scores["by_phase"]) == set(control_scores["by_phase"]), "phase pairing mismatch")
    for phase, ref in reference_scores["by_phase"].items():
        ctl = control_scores["by_phase"][phase]
        mice = sorted(ref["per_mouse"])
        require(mice == sorted(ctl["per_mouse"]), "mouse pairing mismatch")
        for mouse in mice:
            for key in ("n_packets", "expected_binding_sha256", "class_packet_counts"):
                require(ref["per_mouse"][mouse][key] == ctl["per_mouse"][mouse][key], "paired expected items or labels mismatch")
        estimates = {}
        indices = rng.integers(0, len(mice), (draws, len(mice))) if len(mice) >= 2 else None
        for metric in ("log_loss", "balanced_accuracy"):
            rv = np.array([ref["per_mouse"][m][metric] for m in mice])
            cv = np.array([ctl["per_mouse"][m][metric] for m in mice])
            for label, values in (("neural", rv), ("movement_position", cv), ("neural_minus_control", rv-cv)):
                estimates[f"{label}_{metric}"] = {"estimate": float(values.mean()), "percentile_95_ci":
                    np.quantile(values[indices].mean(axis=1), [0.025, 0.975]).tolist() if indices is not None else None}
        output[phase] = {"paired_mice": mice, "replication": "mouse_cluster_bootstrap" if indices is not None else "single_mouse_descriptive_only", "metrics": estimates}
    return output


def evaluate(sessions, plan, bootstrap_draws=2000):
    started = time.perf_counter()
    train, evaluation, audit = prepare(sessions, plan)
    public_query = query(evaluation)
    neural = Reference(plan["classes"], "neural").fit(train).predict(public_query)
    control = Reference(plan["classes"], "context").fit(train).predict(public_query)
    neural_scores = score(evaluation, neural, plan["classes"])
    control_scores = score(evaluation, control, plan["classes"])
    report = {"task_id": "NEURAL-027", "implementation": "initial-evaluator-v1", "scientific_qualification": "unknown",
              "development_only": True, "protocol_status": "prospective_engineering_reference", "holds": HOLDS,
              "classes_in_probability_order": plan["classes"], "neural": neural_scores, "movement_position": control_scores,
              "paired_uncertainty": compare(neural_scores, control_scores, draws=bootstrap_draws), "extraction_audit": audit,
              "resources": {"elapsed_seconds": time.perf_counter()-started, "train_packets": len(train), "evaluation_packets": len(evaluation),
                            "scientific_or_authentic_execution_inferred": False}}
    return report, {"neural": neural, "movement_position": control}, public_query


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--session-dir", required=True, type=Path, help="safe numeric NPZ exports, named session_id.npz")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    plan_raw = args.plan.read_bytes()
    plan = json.loads(plan_raw)
    validate_plan(plan)
    sessions, input_pins = [], []
    for meta in plan["sessions"]:
        # Session identifiers are used as a basename, never a path traversal.
        require(Path(meta["session_id"]).name == meta["session_id"] and "/" not in meta["session_id"] and "\\" not in meta["session_id"], "unsafe session filename")
        path = args.session_dir / (meta["session_id"] + ".npz")
        raw = path.read_bytes()
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            require(set(archive.files) == {"spks", "iarea", *SOURCE_FIELDS, "Corridor_Length", "UniqWalls", "stim_id"}, "unexpected/missing safe export fields")
            s = dict(meta, spks=archive["spks"], iarea=archive["iarea"], behavior={k: archive[k] for k in (*SOURCE_FIELDS, "Corridor_Length", "UniqWalls", "stim_id")})
        sessions.append(s)
        input_pins.append({"session_id": meta["session_id"], "bytes": len(raw),
                           "sha256": hashlib.sha256(raw).hexdigest()})
    report, predictions, public_query = evaluate(sessions, plan)
    report["input_pins"] = input_pins
    report["plan_sha256"] = hashlib.sha256(plan_raw).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (("report.json", report), ("predictions.json", predictions), ("public_query.json", public_query)):
        (args.output_dir / name).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
