"""ICNet Fig. 4d vectors against an externally supplied Poisson LNP rate.

This supplies sampling and comparison, not an LNP fit or authentic baseline.
PCG64 sampling, Pearson correlation, ddof and undefined-value handling are
explicit prospective conventions; historical stochastic parity is not claimed.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

SCORER_SHA256 = "c2643973762868391ea1d32b9c7ed54f546740f615db65bb2c920bc4ca9a493a"
METRICS = ("correlation_explained_percent", "variance_explained_percent")
SAMPLING = "prospective_NumPy_PCG64_Poisson_two_explicit_trial_seeds"


def _scorer():
    path = Path(__file__).with_name("scorer.py")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != SCORER_SHA256:
        raise ValueError("source-equation scorer pin changed")
    # Execute exactly the bytes just authenticated, not a second file read.
    spec = importlib.util.spec_from_loader("icnet_comparison_equations", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def poisson_trials(rates, *, trial_seeds):
    """Two unbounded Poisson draws with mean equal to the same LNP rate.

    The source LNP maps the sound to a rate without the ICNet time module.
    Identical sound support therefore shares the rate across repeated trials.
    Seeds are required, recorded choices; they are not source-author seeds.
    """
    values = np.asarray(rates)
    if (values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 1
            or values.dtype.kind not in "iuf"):
        raise ValueError("LNP rates must be a time x unit real matrix")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("LNP rates must be finite and nonnegative")
    if (type(trial_seeds) not in (list, tuple) or len(trial_seeds) != 2
            or any(type(seed) is not int or not 0 <= seed < 2**63
                   for seed in trial_seeds)):
        raise ValueError("two explicit nonnegative integer trial seeds required")
    values = values.astype(np.float64, copy=False)
    samples = tuple(np.random.Generator(np.random.PCG64(seed)).poisson(values)
                    for seed in trial_seeds)
    # Keep int64 Poisson support; never truncate to five classes or cast int8.
    return values, samples


def _join(icnet, lnp):
    """Pair source units and retain undefined results instead of dropping them."""
    for key in ("time_bins", "original_units", "eligible_units", "variance_ddof"):
        if icnet[key] != lnp[key]:
            raise ValueError("ICNet and LNP comparison support differs")
    a = icnet["by_unit"]
    b = lnp["by_unit"]
    if len(a) != len(b):
        raise ValueError("ICNet and LNP unit populations differ")
    vector = []
    for left, right in zip(a, b):
        identity = (left["unit_id"], left["column_zero_based"])
        if identity != (right["unit_id"], right["column_zero_based"]):
            raise ValueError("ICNet and LNP ordered unit identities differ")
        differences = {
            key: (None if left[key] is None or right[key] is None
                  else left[key] - right[key]) for key in METRICS
        }
        vector.append({"unit_id": identity[0], "column_zero_based": identity[1],
                       "icnet": left, "lnp": right,
                       "icnet_minus_lnp_percentage_points": differences})
    return {
        "time_bins": icnet["time_bins"], "original_units": icnet["original_units"],
        "eligible_units": icnet["eligible_units"],
        "fig4d_time_only_unit_vector": vector,
        "fig4b_flattened_companions": {"icnet": icnet["flattened"],
                                      "lnp": lnp["flattened"]},
        "flattened_lnp_scope": "derived companion; source LNP comparison is Fig4d",
    }


def compare_case(recorded_trial1, recorded_trial2, sampled_trial1,
                 sampled_trial2, expected_trial1, expected_trial2, lnp_rates, *,
                 eligible_mask, unit_ids, variance_ddof, lnp_trial_seeds):
    """Same-observation case kernel; no provenance or full-panel qualification."""
    scorer = _scorer()
    kwargs = {"eligible_mask": eligible_mask, "unit_ids": unit_ids,
              "variance_ddof": variance_ddof}
    icnet = scorer.score_case(recorded_trial1, recorded_trial2, sampled_trial1,
                             sampled_trial2, expected_trial1, expected_trial2,
                             **kwargs)
    rates, samples = poisson_trials(lnp_rates, trial_seeds=lnp_trial_seeds)
    lnp = scorer.score_case(recorded_trial1, recorded_trial2, *samples,
                           rates, rates, **kwargs)
    return {"qualification": "paired_case_equation_component_only",
            "sampling": SAMPLING, "lnp_trial_seeds": list(lnp_trial_seeds),
            "variance_ddof": variance_ddof, **_join(icnet, lnp)}


def score_comparison_panel(manifest, input_root):
    """Pair the original 28 animal/sound cases without selecting easy units.

    All model and training evidence hashes are declarations, not authentication.
    LNP rate arrays are hash-checked, but no fit, architecture or split is proved.
    """
    if (type(manifest) is not dict or set(manifest) != {"schema", "icnet_panel", "lnp"}
            or manifest["schema"] != "icnet-fig4-lnp-comparison-input/v1"):
        raise ValueError("unsupported comparison input")
    scorer = _scorer()
    lnp = manifest["lnp"]
    if (type(lnp) is not dict or set(lnp) != {
            "model_sha256_by_animal", "training_split_evidence_sha256",
            "sampling", "cases"} or lnp["sampling"] != SAMPLING):
        raise ValueError("explicit Poisson LNP provenance and sampling required")
    model_pins = lnp["model_sha256_by_animal"]
    if (type(model_pins) is not dict
            or set(model_pins) != {str(a) for a in scorer.ANIMALS}
            or not all(scorer._sha(pin) for pin in model_pins.values())
            or not scorer._sha(lnp["training_split_evidence_sha256"])):
        raise ValueError("seven LNP model pins and training-split evidence required")
    expected = {(a, s) for a in scorer.ANIMALS for s in scorer.SOUNDS}
    lnp_cases = {}
    if type(lnp["cases"]) is not list or len(lnp["cases"]) != len(expected):
        raise ValueError("all 28 LNP cases required")
    for case in lnp["cases"]:
        if type(case) is not dict or set(case) != {
                "animal", "sound", "time_bins", "rates", "trial_seeds"}:
            raise ValueError("invalid LNP case fields")
        key = (case["animal"], case["sound"])
        if (type(key[0]) is not int or key not in expected or key in lnp_cases
                or type(case["time_bins"]) is not int):
            raise ValueError("duplicate, foreign or invalid LNP case")
        lnp_cases[key] = case
    # Retained validation covers masks, original IDs, all 28 cases, observed
    # trial identities, expected versus sampled arrays and ICNet source hashes.
    panel = manifest["icnet_panel"]
    icnet_report = scorer.score_panel(panel, input_root)
    source_cases = {(c["animal"], c["sound"]): c for c in panel["cases"]}
    root = Path(input_root).resolve()
    results = []
    for icnet in icnet_report["cases"]:
        key = (icnet["animal"], icnet["sound"])
        original, comparator = source_cases[key], lnp_cases[key]
        if comparator["time_bins"] != original["time_bins"]:
            raise ValueError("LNP and ICNet temporal support differs")
        with ExitStack() as stack:
            rates = stack.enter_context(scorer._load_array(root, comparator["rates"]))
            if rates.shape != (original["time_bins"], 512):
                raise ValueError("LNP rate columns or temporal support differ")
            rates, samples = poisson_trials(rates, trial_seeds=comparator["trial_seeds"])
            observed = [stack.enter_context(scorer._load_array(root, original["arrays"][name]))
                        for name in ("recorded_trial1", "recorded_trial2")]
            animal = panel["animals"][str(key[0])]
            lnp_scores = scorer.score_case(
                *observed, *samples, rates, rates,
                eligible_mask=animal["eligible_mask"], unit_ids=animal["unit_ids"],
                variance_ddof=panel["variance_ddof"])
        results.append({"animal": key[0], "sound": key[1],
                        "measurement_times_seconds": original["measurement_times_seconds"],
                        "lnp_rates": comparator["rates"],
                        "lnp_trial_seeds": comparator["trial_seeds"],
                        **_join(icnet, lnp_scores)})
    return {
        "schema": "icnet-fig4-lnp-comparison-result/v1",
        "qualification": "source_defined_vector_component_only",
        "scorer_sha256": SCORER_SHA256,
        "endpoint_binding": icnet_report["endpoint_binding"],
        "sampling": SAMPLING, "numpy_version": np.__version__,
        "variance_ddof": panel["variance_ddof"],
        "source_preparation_pins": icnet_report["preparation_pins"],
        "lnp_model_sha256_by_animal": model_pins,
        "lnp_training_split_evidence_sha256": lnp["training_split_evidence_sha256"],
        "n_animals": 7, "n_sounds": 4, "eligible_units": 3476, "cases": results,
        "difference_direction": "positive means ICNet exceeds LNP for that unit and metric",
        "inference": "descriptive source comparison only; no superiority decision",
        "universal_scalar_required": False,
        "unverified": ["model architecture and fitted rates", "original development split",
                       "authentic observations, mask, time and crop joins",
                       "historical TensorFlow sampling parity and reference values",
                       "source boxplot conventions and companion reproduction",
                       "protected exposure, uncertainty and improvement decision"],
        "model_provenance_authenticated": False,
        "historical_sampling_parity": False,
        "native_author_baseline_reproduced": False,
        "reproduction_evaluated": False, "improvement_evaluated": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    body = args.manifest.read_bytes()
    report = score_comparison_panel(json.loads(body), args.input_root)
    report["input_manifest_sha256"] = hashlib.sha256(body).hexdigest()
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
