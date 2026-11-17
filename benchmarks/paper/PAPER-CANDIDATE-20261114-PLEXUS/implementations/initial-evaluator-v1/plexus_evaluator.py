"""Prospective complete-screen, held-plate evaluation; no model fitting or data fetching."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean
from typing import Any

TASK_ID = "PAPER-CANDIDATE-20261114-PLEXUS"
METHODS = ("network", "single_cell", "manual_features", "nuisance_only", "label_shuffle_refit")
RECORD = "10.5281/zenodo.15809433"
CONTRACT_SHA256 = "125009ce994e355a227ce6cf87ab2923a43336ea7dbfe216afdadbcc46b25ef7"
ALPHA = 0.05
CELL_LINES = ("WT-WTC11", "Mutant-WTC11", "WT-Patient Line", "Mutant-Patient Line")


class ContractError(ValueError):
    """Input violates the frozen evaluation population or prospective policy."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def string(value: Any, field: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{field} must be nonempty text")
    return value


def pin(value: Any, field: str) -> str:
    require(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value), f"{field} must be a SHA256")
    return value


def well_key(row: dict) -> tuple[str, str, str, str]:
    return tuple(row[k] for k in ("cell_line", "batch", "plate", "well"))


def plate_key(row: dict) -> tuple[str, str, str]:
    return well_key(row)[:3]


def score_key(row: dict) -> tuple[str, str, str, str, str, str]:
    return (row["method"], row["target_gene"], *well_key(row))


def auroc(labels: list[int], scores: list[float]) -> float | None:
    """Mann–Whitney pair probability; ties count one half, no class pooling."""
    require(len(labels) == len(scores), "label/score length mismatch")
    pos = [s for y, s in zip(labels, scores) if y == 1]
    neg = [s for y, s in zip(labels, scores) if y == 0]
    if not pos or not neg:
        return None
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def binary_metrics(labels: list[int], scores: list[float]) -> dict:
    """Well weighted within one plate, preserving its observed class prevalence."""
    require(bool(labels) and len(labels) == len(scores), "empty/mismatched binary metric inputs")
    require(all(type(y) is int and y in (0, 1) for y in labels), "labels must be binary integers")
    require(all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in scores), "scores must be finite probabilities")
    controls = [p for y, p in zip(labels, scores) if y == 0]
    treated = [p for y, p in zip(labels, scores) if y == 1]
    ece = 0.0
    for b in range(10):
        ids = [i for i, p in enumerate(scores) if min(9, int(p * 10)) == b]
        if ids:
            ece += len(ids) / len(scores) * abs(mean(scores[i] for i in ids) - mean(labels[i] for i in ids))
    return {
        "n_wells": len(labels), "n_target_wells": sum(labels), "n_control_wells": len(controls),
        "prevalence": mean(labels), "auroc": auroc(labels, scores),
        "brier": mean((p-y)**2 for y, p in zip(labels, scores)), "ece_10_fixed_bins": ece,
        "control_brier": mean(p*p for p in controls) if controls else None,
        "control_mean_probability": mean(controls) if controls else None,
        "control_positive_rate_at_0_5": mean(p >= 0.5 for p in controls) if controls else None,
        "score_separation": mean(treated)-mean(controls) if treated and controls else None,
    }


def by_adjust(p_values: list[float]) -> list[float]:
    """Benjamini–Yekutieli q values; complete prespecified family, arbitrary dependence."""
    require(bool(p_values) and all(math.isfinite(p) and 0 <= p <= 1 for p in p_values), "invalid p-value family")
    m = len(p_values)
    harmonic = sum(1.0 / i for i in range(1, m+1))
    order = sorted(range(m), key=lambda i: p_values[i])
    out = [1.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank-1]
        running = min(running, p_values[idx] * m * harmonic / rank)
        out[idx] = running
    return out


def seed_for(seed: int, *parts: str) -> int:
    return int(hashlib.sha256((str(seed) + "|" + "|".join(parts)).encode()).hexdigest()[:16], 16)


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    x = q * (len(ordered)-1)
    lo = int(x)
    hi = min(lo+1, len(ordered)-1)
    return ordered[lo] + (x-lo) * (ordered[hi]-ordered[lo])


def cluster_interval(plate_values: list[tuple[str, float]], repeats: int, seed: int) -> dict:
    """Resample independent batches, retaining every plate in each sampled batch."""
    clusters: dict[str, list[float]] = defaultdict(list)
    for batch, value in plate_values:
        clusters[batch].append(value)
    result = {"estimate": mean(v for _, v in plate_values) if plate_values else None,
              "n_batches": len(clusters), "n_plates": len(plate_values), "ci95": None}
    if len(clusters) < 2:
        result["status"] = "unavailable_fewer_than_two_independent_batches"
        return result
    rng = random.Random(seed)
    names = sorted(clusters)
    samples = []
    for _ in range(repeats):
        selected = [rng.choice(names) for _ in names]
        samples.append(mean(v for name in selected for v in clusters[name]))
    result.update(status="estimated_batch_cluster_percentile", ci95=[percentile(samples, .025), percentile(samples, .975)])
    return result


def _plate_separation(rows: list[dict], labels: list[int], scores: list[float]) -> float | None:
    by_plate: dict[tuple, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        by_plate[plate_key(row)].append(i)
    values = []
    for ids in by_plate.values():
        target = [scores[i] for i in ids if labels[i] == 1]
        control = [scores[i] for i in ids if labels[i] == 0]
        if target and control:
            values.append(mean(target)-mean(control))
    return mean(values) if values else None


def blocked_randomization(rows: list[dict], labels: list[int], scores: list[float], approved: bool, repeats: int, seed: int) -> dict:
    """One-sided fixed-score randomization; labels permute only within declared blocks.

    This is conditional on the curator's well-level exchangeability assertion. It
    does not retrain a model and is distinct from the label_shuffle_refit comparator.
    """
    if not approved:
        return {"status": "unavailable_exchangeability_not_established", "p_value": None}
    blocks: dict[tuple, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        blocks[(*plate_key(row), row["exchangeability_block"])].append(i)
    mixed = [ids for ids in blocks.values() if {labels[i] for i in ids} == {0, 1}]
    if not mixed:
        return {"status": "unavailable_no_label_mixed_blocks", "p_value": None}
    observed = _plate_separation(rows, labels, scores)
    if observed is None:
        return {"status": "unavailable_no_two_class_plates", "p_value": None}
    rng = random.Random(seed)
    exceed = 0
    for _ in range(repeats):
        shuffled = labels[:]
        for ids in mixed:
            values = [labels[i] for i in ids]
            rng.shuffle(values)
            for i, value in zip(ids, values):
                shuffled[i] = value
        null = _plate_separation(rows, shuffled, scores)
        # Per-block class counts are preserved; therefore two-class plate coverage is fixed.
        exceed += null >= observed - 1e-15
    return {"status": "tested_conditional_on_declared_exchangeability", "p_value": (exceed+1)/(repeats+1),
            "alternative": "positive_score_separation", "n_mixed_blocks": len(mixed),
            "n_label_movable_wells": sum(map(len, mixed)), "permutations": repeats, "minimum_p": 1/(repeats+1)}


def validate(manifest: dict, submission: dict, expected_manifest_sha256: str) -> tuple[list[dict], dict, list[str], list[str]]:
    require(canonical_hash(manifest) == pin(expected_manifest_sha256, "manifest pin"), "manifest SHA256 does not match independently frozen pin")
    require(manifest.get("task_id") == TASK_ID, "wrong task")
    require(manifest.get("dataset_record") == RECORD, "v2 data identity required; v1 cannot be substituted")
    require(manifest.get("contract_sha256") == CONTRACT_SHA256, "wrong scientific contract")
    genes, lines = manifest.get("genes"), manifest.get("cell_lines")
    require(isinstance(genes, list) and len(genes) == 52 and len(set(genes)) == 52, "complete exactly 52 distinct genes required")
    require(isinstance(lines, list) and len(lines) == 4 and set(lines) == set(CELL_LINES), "all four released cell-line strata required")
    for value in genes + lines:
        string(value, "gene/cell_line")
    for field in ("population_source_sha256", "cell_line_mapping_sha256", "split_plan_sha256", "exchangeability_design_sha256"):
        pin(manifest.get(field), field)
    require(type(manifest.get("exchangeability_approved")) is bool, "exchangeability approval must be boolean")
    string(manifest.get("population_scope"), "population_scope")
    wells = manifest.get("wells")
    require(isinstance(wells, list) and bool(wells), "complete well census required")
    keys = set()
    physical_wells = set()
    physical_plate_batches = {}
    batches: dict[tuple, set] = defaultdict(set)
    plate_roles: dict[tuple, set] = defaultdict(set)
    observed_genes, observed_lines = set(), set()
    for row in wells:
        for field in ("cell_line", "batch", "plate", "well", "guide", "exchangeability_block"):
            string(row.get(field), field)
        require(row["cell_line"] in lines, "unlisted cell line")
        require(row.get("role") in ("train", "dev", "test"), "invalid split role")
        require(type(row.get("is_control")) is bool, "control status must be boolean")
        require(type(row.get("eligible")) is bool, "eligibility must be boolean")
        require(type(row.get("n_cells")) is int and row["n_cells"] >= 0, "n_cells must be a nonnegative integer")
        if row["eligible"]:
            require(row["n_cells"] > 0 and row.get("exclusion_reason") is None, "eligible well needs cells and no exclusion")
        else:
            string(row.get("exclusion_reason"), "exclusion_reason")
        if row["is_control"]:
            require(row.get("gene") is None, "negative control cannot carry a target gene")
        else:
            require(row.get("gene") in genes, "unknown or absent target gene")
            observed_genes.add(row["gene"])
        observed_lines.add(row["cell_line"])
        key = well_key(row)
        require(key not in keys, f"duplicate well {key}")
        keys.add(key)
        # IDs name physical batches/plates globally, even when lines share them.
        physical_well = (row["plate"], row["well"])
        require(physical_well not in physical_wells, "physical well duplicated across line/batch aliases")
        physical_wells.add(physical_well)
        require(row["plate"] not in physical_plate_batches or physical_plate_batches[row["plate"]] == row["batch"], "physical plate aliases multiple batches")
        physical_plate_batches[row["plate"]] = row["batch"]
        batches[row["batch"]].add(row["role"])
        plate_roles[row["plate"]].add(row["role"])
    require(observed_genes == set(genes), "census omits one or more of the 52 genes")
    require(observed_lines == set(lines), "census omits a declared cell line")
    require(all(len(v) == 1 for v in batches.values()), "batch leakage across train/dev/test")
    require(all(len(v) == 1 for v in plate_roles.values()), "plate leakage across train/dev/test")
    require(any(r["role"] == "test" and r["eligible"] for r in wells), "no eligible held wells")
    require(submission.get("manifest_sha256") == expected_manifest_sha256, "submission uses a different manifest")
    require(submission.get("policy") == "prospective-held-plate-v1", "historical and prospective results cannot be conflated")
    require(submission.get("fdr_alpha") == ALPHA, "frozen FDR alpha is 0.05")
    models = submission.get("models")
    require(isinstance(models, dict) and set(models) == set(METHODS), "all three scientific and two control methods required")
    train_keys = {well_key(r) for r in wells if r["role"] == "train" and r["eligible"]}
    for method, provenance in models.items():
        for field in ("source_sha256", "configuration_sha256", "fitted_artifact_sha256", "tuning_plan_sha256"):
            pin(provenance.get(field), f"{method}.{field}")
        require(provenance.get("input_basis") == ("metadata_only" if method == "nuisance_only" else "processed_neuronal_inputs"), f"invalid input basis for {method}")
        require(provenance.get("checkpoint_exposure") == "train_only", f"held-data-trained checkpoints forbidden for {method}")
        for field in ("fit_wells", "statistics_wells"):
            values = provenance.get(field)
            require(isinstance(values, list) and bool(values), f"{method}.{field} must record training lineage")
            require(all(isinstance(k, list) and len(k) == 4 and all(isinstance(v,str) for v in k) for k in values), "invalid lineage well key")
            require(len({tuple(k) for k in values}) == len(values), "duplicate lineage well")
            require({tuple(k) for k in values} <= train_keys, f"non-training fit/statistics exposure in {method}")
        require(provenance.get("frozen_before_held_labels") is True, f"{method} freeze declaration required")
        if method == "label_shuffle_refit":
            pin(provenance.get("training_label_shuffle_plan_sha256"), "training-label shuffle plan")
    scores = submission.get("scores")
    require(isinstance(scores, list), "keyed scores required")
    held = [r for r in wells if r["role"] == "test" and r["eligible"]]
    expected = {(m, g, *well_key(r)) for m in METHODS for g in genes for r in held if r["is_control"] or r["gene"] == g}
    observed = {}
    for row in scores:
        for field in ("method", "target_gene", "cell_line", "batch", "plate", "well"):
            string(row.get(field), field)
        key = score_key(row)
        require(key not in observed, f"duplicate prediction {key}")
        probability = row.get("probability")
        require(type(probability) in (int, float) and math.isfinite(probability) and 0 <= probability <= 1, "score must be a finite probability in [0,1]")
        observed[key] = float(probability)
    require(set(observed) == expected, f"score population mismatch: {len(expected-set(observed))} missing; {len(set(observed)-expected)} unexpected")
    return held, observed, sorted(genes), sorted(lines)


def evaluate(manifest: dict, submission: dict, expected_manifest_sha256: str, *, permutations: int = 49999, bootstraps: int = 1999, seed: int = 0) -> dict:
    require(type(permutations) is int and 1 <= permutations <= 1000000, "permutations must be 1..1000000")
    require(type(bootstraps) is int and 2 <= bootstraps <= 100000, "bootstraps must be 2..100000")
    require(type(seed) is int, "seed must be an integer")
    held, scores, genes, lines = validate(manifest, submission, expected_manifest_sha256)
    table, plates, guides, comparators = [], [], [], []
    lookup = {}
    for method in METHODS:
        method_rows = []
        for line in lines:
            for gene in genes:
                rows = sorted([r for r in held if r["cell_line"] == line and (r["is_control"] or r["gene"] == gene)], key=well_key)
                grouped: dict[tuple, list[dict]] = defaultdict(list)
                for row in rows:
                    grouped[plate_key(row)].append(row)
                plate_results = []
                for key, group in sorted(grouped.items()):
                    labels = [int(not r["is_control"]) for r in group]
                    probabilities = [scores[(method, gene, *well_key(r))] for r in group]
                    result = {"method": method, "gene": gene, "cell_line": line, "batch": key[1], "plate": key[2], **binary_metrics(labels, probabilities)}
                    result["status"] = "scored" if result["auroc"] is not None else "unavailable_single_class_plate"
                    plate_results.append(result)
                    plates.append(result)
                # Preserve guide-specific heterogeneity under the same frozen gene classifier.
                # These are descriptive prospective slices, not historical per-guide fits.
                target_guides = sorted({r["guide"] for r in rows if not r["is_control"]})
                for guide in target_guides:
                    for key, group in sorted(grouped.items()):
                        subset = [r for r in group if r["is_control"] or r["guide"] == guide]
                        if not any(not r["is_control"] for r in subset):
                            continue
                        guides.append({"method": method, "gene": gene, "guide": guide, "cell_line": line,
                                       "batch": key[1], "plate": key[2],
                                       **binary_metrics([int(not r["is_control"]) for r in subset],
                                                        [scores[(method, gene, *well_key(r))] for r in subset])})
                paired = [r for r in plate_results if r["auroc"] is not None]
                labels = [int(not r["is_control"]) for r in rows]
                probabilities = [scores[(method, gene, *well_key(r))] for r in rows]
                inference = blocked_randomization(rows, labels, probabilities, manifest["exchangeability_approved"], permutations, seed_for(seed, method, line, gene, "randomization"))
                row = {"method": method, "gene": gene, "cell_line": line,
                       "status": "scored" if paired else "unavailable_no_two_class_plates",
                       "n_two_class_plates": len(paired), "n_single_class_plates": len(plate_results)-len(paired),
                       "n_target_wells": sum(labels), "n_control_wells": len(labels)-sum(labels),
                       "plate_macro_auroc": mean(r["auroc"] for r in paired) if paired else None,
                       "plate_macro_brier": mean(r["brier"] for r in plate_results) if plate_results else None,
                       "score_separation": cluster_interval([(r["batch"], r["score_separation"]) for r in paired], bootstraps, seed_for(seed, method, line, gene, "effect")),
                       "randomization": inference}
                row["multiplicity_p"] = inference["p_value"] if inference["p_value"] is not None else 1.0
                method_rows.append(row)
                lookup[(method, line, gene)] = plate_results
        adjusted = by_adjust([r["multiplicity_p"] for r in method_rows])
        for row, q in zip(method_rows, adjusted):
            row.update(q_by=q, rejected_at_fdr_0_05=row["randomization"]["p_value"] is not None and q <= ALPHA)
        table.extend(method_rows)
    for baseline in METHODS[1:]:
        for line in lines:
            for gene in genes:
                network = {(r["batch"], r["plate"]): r for r in lookup[("network", line, gene)]}
                other = {(r["batch"], r["plate"]): r for r in lookup[(baseline, line, gene)]}
                require(set(network) == set(other), "comparator plate population mismatch")
                metrics = {}
                for metric in ("auroc", "brier", "score_separation"):
                    valid = [k for k in sorted(network) if network[k][metric] is not None and other[k][metric] is not None]
                    metrics["network_minus_"+metric] = cluster_interval([(k[0], network[k][metric]-other[k][metric]) for k in valid], bootstraps, seed_for(seed, baseline, line, gene, metric))
                    metrics["network_minus_"+metric]["population"] = "all eligible plates" if metric == "brier" else "two-class plates only"
                comparators.append({"baseline": baseline, "cell_line": line, "gene": gene, "metrics": metrics})
    return {"task_id": TASK_ID, "implementation": "initial-evaluator-v1", "policy": "prospective-held-plate-v1",
            "manifest_sha256": expected_manifest_sha256, "submission_sha256": canonical_hash(submission),
            "scientific_qualification": "unknown", "historical_reproduction": "not_established",
            "native_model_execution": "not_performed", "fdr": {"procedure": "Benjamini-Yekutieli", "alpha": ALPHA,
                "family": "52 genes x all manifest cell lines, separately for each method", "family_size": len(genes)*len(lines),
                "unavailable_endpoint_p": 1.0, "minimum_randomization_p": 1/(permutations+1)},
            "resources": {"permutations_per_endpoint": permutations, "bootstrap_replicates_per_interval": bootstraps, "seed": seed,
                "models_fit": 0, "dataset_bytes_downloaded": 0},
            "census": {"genes": genes, "cell_lines": lines, "wells": len(manifest["wells"]), "eligible_held_wells": len(held),
                "held_cells_descriptive_only": sum(r["n_cells"] for r in held),
                "exclusions": [r for r in manifest["wells"] if not r["eligible"]]},
            "gene_line_table": table, "plate_table": plates, "guide_plate_table": guides, "paired_comparisons": comparators,
            "limitations": ["The frozen manifest and model lineage declarations require independent authentic audit.",
                "Randomization assumes curator-established within-block well-label exchangeability.",
                "Probability separation is predictive separation, not biological phenotype effect size.",
                "Confidence intervals assume independent batches and do not establish cross-line transfer.",
                "Published estimator, complete v1/v2 population reconciliation and native neural input processing remain held."]}


def read_json(path: str) -> dict:
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON field {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=reject_duplicates,
                      parse_constant=lambda value: (_ for _ in ()).throw(ContractError(f"invalid JSON number {value}")))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-sha256", required=True, help="Independently frozen canonical JSON SHA256; never derived from a submitted manifest")
    parser.add_argument("--submission", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--permutations", type=int, default=49999)
    parser.add_argument("--bootstraps", type=int, default=1999)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    try:
        report = evaluate(read_json(args.manifest), read_json(args.submission), args.manifest_sha256,
                          permutations=args.permutations, bootstraps=args.bootstraps, seed=args.seed)
        Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    except (ContractError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"contract error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
