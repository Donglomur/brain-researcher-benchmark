"""Operator-only bridge from fixed Table 1 targets to original author-law fits.

Construction source, not an admitted scientific execution or qualified baseline.
Only the CLI loads the external hash-pinned author module. Tests inject a backend.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
import math
from numbers import Real
from pathlib import Path

AUTHOR_SHA256 = "bd7556bc912d0443f2c00c74cd6f9174a2afb9d1734ceb7cf02b10685abf209b"
AUTHOR_BYTES = 4681
AUTHOR_REVISION = "76464a9ca15564897e58256081af4b99d08ae8db"
AUTHOR_URL = ("https://raw.githubusercontent.com/GWeindel/decision-times/"
              + AUTHOR_REVISION + "/models.py")
_dependencies = {
    "contrast-panel-v2/panel.py": (14807, "7ad801136f12e66c477ab96270159ffd6c4723465af9a684edbd020e51cbdbec"),
    "initial-evaluator-v1/evaluator.py": (25780, "2cbfa3be223cdef714619c2db287bb77de0833c40f9c0c7e20044e6cc272e9f9"),
}
for _relative, (_size, _sha) in _dependencies.items():
    with (Path(__file__).resolve().parents[1] / _relative).open("rb") as _handle:
        _body = _handle.read(_size + 1)
    if len(_body) != _size or hashlib.sha256(_body).hexdigest() != _sha:
        raise ValueError("task dependency identity mismatch: " + _relative)
_spec = importlib.util.spec_from_file_location(
    "decision_times_panel", Path(__file__).resolve().parents[1] / "contrast-panel-v2" / "panel.py")
panel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(panel)
require = panel.require


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def finite(value, label):
    require(isinstance(value, Real) and not isinstance(value, bool)
            and math.isfinite(value), label + ": finite real required")
    return float(value)


def vector(values, size, label):
    require(not isinstance(values, (str, bytes, dict)), label + ": vector required")
    try:
        result = [finite(v, label) for v in values]
    except TypeError as exc:
        raise ValueError(label + ": vector required") from exc
    require(len(result) == size, label + ": wrong vector length")
    return result


def fit_jobs(prepared):
    """Yield source per-person fits, retaining trial weights and global queries.

    Each full-data fit predicts the entire global grid. Each omitted contrast
    also fits each person and predicts that grid, even if that person has no
    observation at the omitted contrast. No means replace the original trials.
    """
    for law in panel.AUTHOR_MODELS:
        for (target, condition), item in prepared.items():
            by_person = defaultdict(list)
            for row in item["rows"]:
                by_person[row["participant"]].append(row)
            for participant in item["participants"]:
                rows = by_person[participant]
                for omitted in [None] + item["contrasts"]:
                    selected = [r for r in rows if r["contrast_percent"] != omitted]
                    require(selected, "empty source fit")
                    job = dict(law=law, target=target, condition=condition,
                        participant=participant,
                        mode="full_data" if omitted is None else "held_out",
                        omitted_contrast_percent=omitted,
                        fit_trial_keys=[[r["participant"], r["epoch"]] for r in selected],
                        fit_contrasts_percent=sorted({r["contrast_percent"] for r in selected}),
                        contrast_fraction=[r["contrast_percent"] / 100 for r in selected],
                        latency_seconds=[r["values"][target] / 1000 for r in selected],
                        prediction_contrasts_percent=list(item["contrasts"]))
                    job["fit_input_sha256"] = digest(job)
                    yield job


def _checked_result(result, law, grid):
    require(isinstance(result, dict), "backend result must be a mapping")
    pars = vector(result.get("parameters"), 3 if law == "fechner" else 2, "parameters")
    if law == "pieron":
        require(all(v >= 0 for v in pars), "Pieron parameters outside source bounds")
    elif law == "fechner":
        require(all(0 <= p <= hi for p, hi in zip(pars, (18.51, 7.47, 3.69))),
                "Fechner parameters outside source bounds")
    observed_grid = vector(result.get("contrast_fraction"), len(grid), "returned contrast")
    require(observed_grid == grid, "backend changed prediction contrast grid")
    latency = vector(result.get("latency_seconds"), len(grid), "predicted latency")
    mse = finite(result.get("training_mse_seconds2"), "training MSE")
    require(mse >= 0, "negative training MSE")
    accuracy = result.get("probability_correct")
    if law == "fechner":
        accuracy = vector(accuracy, len(grid), "Fechner accuracy")
        require(all(0 <= v <= 1 for v in accuracy), "Fechner accuracy outside [0,1]")
    else:
        require(accuracy is None, "only source Fechner has accuracy prediction")
    return pars, latency, accuracy, mse


def produce(targets, backend):
    """Produce all three author methods or raise without returning a partial panel.

    ``backend.fit_predict`` receives source trial vectors in seconds/fractions.
    An injected backend is an engineering seam, not authenticated author code.
    Hash-pinned loading and a completed call still do not qualify source targets,
    historical optimizer parity, baseline competence or independent execution.
    """
    prepared = panel.prepare(targets)
    target_sha = panel.target_digest(targets)
    methods = {law: dict(method_id=law, targets_sha256=target_sha,
        latency_selection="all_responded", time_unit="ms", contrast_unit="percent",
        full_data=[], held_out=[]) for law in panel.AUTHOR_MODELS}
    receipts = []
    for job in fit_jobs(prepared):
        grid = [x / 100 for x in job["prediction_contrasts_percent"]]
        # Independent copies prevent a backend from changing the operator's
        # selected inputs, grid or receipt after the call.
        result = backend.fit_predict(job["law"], list(job["latency_seconds"]),
            list(job["contrast_fraction"]), list(grid))
        pars, latency, accuracy, mse = _checked_result(result, job["law"], grid)
        selected_indices = range(len(grid)) if job["mode"] == "full_data" else [
            job["prediction_contrasts_percent"].index(job["omitted_contrast_percent"])]
        for index in selected_indices:
            row = dict(target=job["target"], condition=job["condition"],
                participant=job["participant"],
                contrast_percent=job["prediction_contrasts_percent"][index],
                fit_contrasts_percent=list(job["fit_contrasts_percent"]),
                latency_ms=finite(latency[index] * 1000, "millisecond prediction"))
            if accuracy is not None:
                row["probability_correct"] = accuracy[index]
            methods[job["law"]][job["mode"]].append(row)
        receipts.append({k: job[k] for k in ("law", "target", "condition", "participant",
            "mode", "omitted_contrast_percent", "fit_input_sha256")})
        receipts[-1].update(fit_trials=len(job["fit_trial_keys"]),
            fit_contrasts_percent=list(job["fit_contrasts_percent"]),
            parameters=pars, training_mse_seconds2=mse,
            full_prediction_sha256=digest(result))
    references = [methods[law] for law in panel.AUTHOR_MODELS]
    # Reuse the existing independent geometry/finite/fold checks. This is not
    # source reference authentication and no biological result is computed here.
    for method in references:
        panel._predictions(method, prepared, "held_out")
        panel._predictions(method, prepared, "full_data", method["method_id"] == "fechner")
    return dict(schema="decision-times-author-reference-production-v1",
        task_id=panel.legacy.TASK, targets_sha256=target_sha,
        purpose=targets["hmp"]["purpose"], author_revision=AUTHOR_REVISION,
        backend_identity=backend.identity(), references=references,
        fit_receipts=receipts, completed_fit_count=len(receipts),
        qualification="unqualified_operator_reference_production",
        readiness_promoted=False, paper_win=None, current_sota="not_assessed",
        limitations=[
            "Source target/B-H cohort lineage, 512-Hz HMP parity and optimizer environment are unqualified.",
            "Fit inputs preserve trial weighting; the original latent targets remain fixed, not newly estimated.",
            "Generated backend tests do not fit any model or establish source numerical reproduction.",
            "This artifact is operator-private and contains parameters/predictions; never deliver it to participants.",
            "No tolerance, joint18-cell improvement rule, biological uncertainty or protected execution is admitted."])


class AuthorBackend:
    """Calls the original class with exactly one fit per supplied trial vector."""
    def __init__(self, namespace, numpy_module, source_hash, versions):
        self.factory = namespace["latency"]
        self.np = numpy_module
        self.source_hash = source_hash
        self.versions = versions

    def identity(self):
        return dict(kind="hash_pinned_original_models_module", source_sha256=self.source_hash,
            source_url=AUTHOR_URL, runtime_versions=dict(self.versions),
            independent_execution_attestation=False)

    def fit_predict(self, law, latencies, contrasts, grid):
        model = self.factory(law, latencies=self.np.asarray(latencies, dtype=float),
            contrast=self.np.asarray(contrasts, dtype=float))
        model.fit()
        query = self.np.asarray(grid, dtype=float)
        xs, ys = model.predictions(query, model.pars)
        accuracy = None
        if law == "fechner":
            ax, accuracy = model.predictions_accuracy(query, model.pars)
            require(list(ax) == list(xs), "source accuracy grid differs")
            accuracy = [float(x) for x in accuracy]
        return dict(parameters=[float(x) for x in model.pars],
            contrast_fraction=[float(x) for x in xs],
            latency_seconds=[float(x) for x in ys], probability_correct=accuracy,
            training_mse_seconds2=float(model.mse))


def load_author_backend(path):
    """Execute only the exact separately acquired source, from its verified bytes.

    No download or installation occurs. This function imports scientific
    dependencies and is reserved for a separately admitted native execution.
    """
    with Path(path).open("rb") as handle:
        raw = handle.read(AUTHOR_BYTES + 1)
    observed = hashlib.sha256(raw).hexdigest()
    require(len(raw) == AUTHOR_BYTES and observed == AUTHOR_SHA256,
            "author models.py identity mismatch")
    import numpy
    from importlib.metadata import version
    versions = {name: version(name) for name in ("numpy", "scipy", "pandas", "matplotlib")}
    namespace = {"__name__": "decision_times_pinned_author", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    require(callable(namespace.get("latency")), "source latency class missing")
    return AuthorBackend(namespace, numpy, observed, versions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", type=Path)
    parser.add_argument("--author-models", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "output already exists")
    raw = args.targets.read_bytes()
    targets = json.loads(raw)
    # Reject malformed target support before importing/executing author code.
    panel.prepare(targets)
    backend = load_author_backend(args.author_models)
    result = produce(targets, backend)
    result["targets_file_sha256"] = hashlib.sha256(raw).hexdigest()
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    with args.output.open("x") as handle:
        handle.write(encoded)


if __name__ == "__main__":
    main()
