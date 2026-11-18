"""Observe the original optimizer boundary without replacing its computation.

Only collect_original/CLI invokes the existing source loader. Generated controls
use collect_injected. Trusted sequential operator use; not process isolation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from numbers import Integral, Real
from pathlib import Path
from types import SimpleNamespace
import warnings

_path = Path(__file__).resolve().parents[1] / "author-law-production-v1/producer.py"
_raw = _path.read_bytes()
if len(_raw) != 12238 or hashlib.sha256(_raw).hexdigest() != "6a9e1afd076ca1ffc9931a49f28a488a34ba53168f6fba7ff41b826d3fa4317e":
    raise ValueError("accepted original producer identity changed")
_spec = importlib.util.spec_from_file_location("decision_times_observed_producer", _path)
source = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(source)
require = source.require

RECIPE = {
    "author_revision": source.AUTHOR_REVISION,
    "models_bytes": source.AUTHOR_BYTES,
    "models_sha256": source.AUTHOR_SHA256,
    "class": "latency", "fit_method": "fit", "optimizer": "scipy.optimize.curve_fit",
    "explicit_keywords": ["p0", "bounds", "full_output"],
    "full_output": True,
    "laws": {
        "linear": {"function": "lm_func", "equation": "slope*x + t0", "p0": [1, 1],
                   "bounds": [["-inf", "-inf"], ["+inf", "+inf"]]},
        "pieron": {"function": "pieron_func", "equation": "slope*x**-alpha", "p0": [1, 1],
                   "bounds": [[0, 0], ["+inf", "+inf"]]},
        "fechner": {"function": "wf_diffusion", "p0": [1, 1, 1],
                    "bounds": [[0, 0, 0], [18.51, 7.47, 3.69]]},
    },
    "units": {"fit_latency": "seconds", "contrast": "fraction"},
    "unspecified_options": "method,tolerances,maxfev,jac,sigma and other options remain runtime defaults; no values inferred",
    "data_helper": "unchanged producer.fit_jobs over unchanged contrast-panel-v2.prepare",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def detached(value):
    return json.loads(canonical(value))


def diagnostic(value):
    """Lossless numeric values, with explicit JSON tags for nonfinite diagnostics."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        if math.isnan(value):
            return {"nonfinite": "nan"}
        if math.isinf(value):
            return {"nonfinite": "+inf" if value > 0 else "-inf"}
        return float(value)
    if isinstance(value, (tuple, list)):
        return [diagnostic(x) for x in value]
    if isinstance(value, dict):
        require(all(isinstance(k, str) for k in value), "diagnostic keys must be strings")
        return {k: diagnostic(v) for k, v in value.items()}
    if callable(getattr(value, "tolist", None)):
        return diagnostic(value.tolist())
    raise ValueError("unsupported diagnostic type: " + type(value).__name__)


def vector(value):
    result = diagnostic(value)
    require(isinstance(result, list) and all(type(x) in (int, float) for x in result),
            "one-dimensional finite fitting vector required")
    return result


def config(law, kwargs):
    require(set(kwargs) == {"p0", "bounds", "full_output"}, "original explicit optimizer keyword set changed")
    require(kwargs["full_output"] is True, "original full_output changed")
    expected = RECIPE["laws"][law]
    observed = diagnostic(kwargs)
    bounds = [[{"nonfinite": x} if isinstance(x, str) else x for x in side]
              for side in expected["bounds"]]
    require(canonical(observed["p0"]) == canonical(expected["p0"])
            and canonical(observed["bounds"]) == canonical(bounds),
            "original starting point or bounds changed")
    return observed


def exception_record(exc):
    return {"type": type(exc).__module__ + "." + type(exc).__qualname__, "message": str(exc)}


def type_record(value):
    result = {"type": type(value).__module__ + "." + type(value).__qualname__}
    if hasattr(value, "dtype"):
        result["dtype"] = str(value.dtype)
    if hasattr(value, "shape"):
        result["shape"] = [int(x) for x in value.shape]
    return result


def warning_filters():
    def expression(value):
        if value is None:
            return None
        return {"pattern": str(getattr(value, "pattern", value)),
                "flags": int(getattr(value, "flags", 0)), "type": type(value).__name__}
    return [dict(action=action, message=expression(message),
                 category=category.__module__ + "." + category.__qualname__,
                 module=expression(module), line=line)
            for action, message, category, module, line in warnings.filters]


class _ObservedBackend:
    def __init__(self, inner, jobs):
        self.inner, self.jobs = inner, iter(jobs)
        self.calls, self.active = [], False

    def identity(self):
        result = detached(self.inner.identity())
        result["observed_recipe_sha256"] = digest(RECIPE)
        result["independent_execution_attestation"] = False
        return result

    def fit_predict(self, law, latencies, contrasts, grid):
        require(not self.active, "collector requires sequential non-reentrant use")
        job = next(self.jobs, None)
        require(job is not None, "unexpected fit beyond source job plan")
        require(law == job["law"] and list(latencies) == job["latency_seconds"]
                and list(contrasts) == job["contrast_fraction"]
                and list(grid) == [x / 100 for x in job["prediction_contrasts_percent"]],
                "backend arguments differ from original source job")
        record = {k: detached(job[k]) for k in ("law", "target", "condition", "participant", "mode",
                  "omitted_contrast_percent", "fit_input_sha256")}
        record.update(status="started", optimizer_calls=[], warnings=[], inherited_warning_filters=warning_filters())
        self.calls.append(record)
        namespace = self.inner.factory.fit.__globals__
        original_scipy = namespace["scipy"]
        original_optimizer = original_scipy.optimize.curve_fit
        self.active = True

        def observe(function, x, y, **kwargs):
            call = {"status": "started", "call_index": len(record["optimizer_calls"]),
                    "function": getattr(function, "__name__", None)}
            record["optimizer_calls"].append(call)
            try:
                require(len(record["optimizer_calls"]) == 1, "more than one original optimizer call")
                require(call["function"] == RECIPE["laws"][law]["function"], "original model function changed")
                actual_x, actual_y = vector(x), vector(y)
                require(actual_x == list(contrasts) and actual_y == list(latencies),
                        "optimizer operands differ from original trial vectors")
                call.update(explicit_kwargs=config(law, kwargs),
                            input_sha256=digest({"contrast_fraction": actual_x, "latency_seconds": actual_y}),
                            input_trials=len(actual_x),
                            input_types={"contrast": type(x).__name__, "latency": type(y).__name__},
                            input_dtypes={"contrast": str(getattr(x, "dtype", "unreported")),
                                          "latency": str(getattr(y, "dtype", "unreported"))})
                # Forward the original objects and exact kwargs once. Neither
                # an optimizer option nor its original five-value result changes.
                returned = original_optimizer(function, x, y, **kwargs)
                require(isinstance(returned, tuple) and len(returned) == 5, "original full_output arity changed")
                call["returned"] = dict(zip(("parameters", "covariance", "info", "message", "status"),
                                            (diagnostic(v) for v in returned)))
                call["return_types"] = dict(zip(("parameters", "covariance", "info", "message", "status"),
                                                (type_record(v) for v in returned)))
                if isinstance(returned[2], dict):
                    call["info_types"] = {k: type_record(v) for k, v in returned[2].items()}
                call["return_sha256"] = digest(call["returned"])
                call["status"] = "returned"
                return returned
            except Exception as exc:
                call.update(status="failed", error=exception_record(exc))
                raise

        proxy = SimpleNamespace(optimize=SimpleNamespace(curve_fit=observe))
        original_showwarning = warnings.showwarning

        def showwarning(message, category, filename, line_number, file=None, line=None):
            record["warnings"].append(dict(category=category.__module__ + "." + category.__qualname__,
                message=str(message), filename=filename, line=line_number))
            # Filtering and registry suppression occur before this handler.
            # Forward every original argument to preserve inherited behavior.
            return original_showwarning(message, category, filename, line_number, file, line)

        try:
            namespace["scipy"] = proxy
            warnings.showwarning = showwarning
            # Do not enter catch_warnings: its filter-version mutations would
            # reset default/once suppression between source fits.
            result = self.inner.fit_predict(law, latencies, contrasts, grid)
            require(len(record["optimizer_calls"]) == 1
                    and record["optimizer_calls"][0]["status"] == "returned", "missing complete original optimizer observation")
            source._checked_result(result, law, grid)
            record.update(status="complete", backend_output_sha256=source.digest(result))
            return result
        except Exception as exc:
            record.update(status="failed", error=exception_record(exc))
            raise
        finally:
            namespace["scipy"] = original_scipy
            warnings.showwarning = original_showwarning
            self.active = False


def _envelope(targets, origin, identity, calls):
    return dict(schema="decision-times-original-optimizer-observation-v1", task_id=source.panel.legacy.TASK,
        operator_only=True, execution_origin=origin, recipe=detached(RECIPE), recipe_sha256=digest(RECIPE),
        targets_sha256=source.panel.target_digest(targets), backend_identity=identity,
        reference_production=None, optimizer_observations=calls,
        warnings_scope="visible_under_inherited_filters_not_all_possible_warnings",
        qualification="execution_provenance_only", scientific_qualification=False, readiness_promoted=False,
        limitations=["Trusted sequential operator execution; namespace/showwarning changes are not concurrent isolation.",
                     "Source helper/B-H target lineage and historical runtime defaults remain unqualified.",
                     "Optimizer status, covariance, warnings and finite results do not establish scientific convergence or reproduction.",
                     "No tolerance, uncertainty or18-cell improvement rule is changed."])


def _collect(targets, backend, origin):
    prepared = source.panel.prepare(targets)
    observed = _ObservedBackend(backend, source.fit_jobs(prepared))
    artifact = _envelope(targets, origin, observed.identity(), observed.calls)
    try:
        require(backend.source_hash == source.AUTHOR_SHA256, "backend does not claim the selected model source")
        result = source.produce(targets, observed)
        require(next(observed.jobs, None) is None, "source fit plan not exhausted")
        require(len(result["fit_receipts"]) == len(observed.calls), "optimizer/producer count mismatch")
        for receipt, call in zip(result["fit_receipts"], observed.calls):
            require(call["status"] == "complete" and receipt["fit_input_sha256"] == call["fit_input_sha256"]
                    and receipt["full_prediction_sha256"] == call["backend_output_sha256"],
                    "optimizer/producer input-output join mismatch")
        artifact.update(status="complete_observation", reference_production=result)
    except Exception as exc:
        artifact.update(status="failed_observation", error=exception_record(exc))
    return detached(artifact)


def collect_injected(targets, backend):
    """Engineering seam: injected evidence never claims original-source execution."""
    return _collect(targets, backend, "injected_backend_no_authentic_execution")


def collect_original(targets, models_path):
    """Separately admitted native route; reuse the existing exact source loader."""
    source.panel.prepare(targets)
    origin = "existing_hash_pinned_source_loader_route_no_independent_attestation"
    try:
        backend = source.load_author_backend(models_path)
    except Exception as exc:
        artifact = _envelope(targets, origin, None, [])
        artifact.update(status="failed_observation", failure_stage="existing_source_loader", error=exception_record(exc))
        return artifact
    return _collect(targets, backend, origin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", type=Path)
    parser.add_argument("--author-models", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "output already exists")
    raw = args.targets.read_bytes()
    result = collect_original(json.loads(raw), args.author_models)
    result["targets_file_sha256"] = hashlib.sha256(raw).hexdigest()
    with args.output.open("x") as handle:
        handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    raise SystemExit(0 if result["status"] == "complete_observation" else 1)


if __name__ == "__main__":
    main()
