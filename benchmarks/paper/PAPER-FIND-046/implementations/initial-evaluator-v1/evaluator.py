#!/usr/bin/env python3
"""PAPER-FIND-046 Figure 2 construction component; no scientific qualification.

The input is an explicit, identity-preserving JSON export of native structures.
This module neither downloads data nor infers a cohort from available files.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
from statistics import mean


TASK_ID = "PAPER-FIND-046"
SOURCE_COMMIT = "b7b68ca8c107d8ce4a061e16da214307f175c3e5"
FIGURE3_RATS = ("G008", "G016", "G021", "G022", "G024", "G036", "G037", "G051", "G127")
STAGES = ("Proestrus", "Diestrus")
LOW_SNR = {("G138", d) for d in ("20240627", "20240701", "20240709")}
HOLDS = [
    "Native archive content, MAT-to-JSON correspondence and all empirical rosters remain unverified.",
    "No authentic MATLAB/reference run, frozen numeric tolerance, or empirical grader is established.",
    "Figure3 supplied BestFits are provenance inputs; RPE encoding and reward-history endpoints are not executed here.",
    "Rat/session grouped improvement assessment and a protected independent panel remain unfrozen.",
    "Cycle stage is observational; hormone associations do not establish causal intervention effects.",
    "Native resource envelope, archive/code rights and public-source model exposure require separate admission.",
]


class ContractError(ValueError):
    """The explicit export cannot be evaluated without changing its meaning."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def number(value, where, *, nullable=False):
    if value is None and nullable:
        return None
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{where}: numeric value required")
    require(math.isfinite(value), f"{where}: nonfinite values must be encoded as JSON null")
    return float(value)


def day(value, where):
    require(isinstance(value, str), f"{where}: date string required")
    fmt = "%Y%m%d" if len(value) == 8 else "%Y-%m-%d"
    try:
        parsed = datetime.strptime(value, fmt)
    except ValueError as exc:
        raise ContractError(f"{where}: expected YYYYMMDD or YYYY-MM-DD") from exc
    require(parsed.strftime(fmt) == value, f"{where}: noncanonical date")
    return parsed.strftime("%Y%m%d")


def roster(value, where):
    require(isinstance(value, list) and value, f"{where}: nonempty explicit roster required")
    require(all(isinstance(x, str) and x for x in value), f"{where}: rat identifiers must be nonempty strings")
    require(len(set(value)) == len(value), f"{where}: duplicate rat identifier")
    return value


def _mean(values):
    finite = [x for x in values if x is not None]
    return mean(finite) if finite else None


def _trace(matrix, indices, width):
    return [_mean([matrix[i][j] for i in indices]) for j in range(width)]


def pearson_complete_vectors(x, y):
    """PlotFigure2 corrcoef default: any missing value makes r undefined."""
    require(len(x) == len(y), "Pearson vectors must have equal lengths")
    if len(x) < 2 or any(v is None for v in x + y):
        return None
    mx, my = mean(x), mean(y)
    dx, dy = [v - mx for v in x], [v - my for v in y]
    xx, yy = sum(v * v for v in dx), sum(v * v for v in dy)
    if xx == 0 or yy == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / math.sqrt(xx * yy)


def unique_object(pairs):
    """Reject duplicate JSON keys before a rat or record can be overwritten."""
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def time_axis(n):
    require(n >= 3, "CPIn must contain at least three signal samples")
    times = [-5.0 + 15.0 * j / (n - 1) for j in range(n)]
    nearest = lambda target: min(range(n), key=lambda j: abs(times[j] - target))
    start, zero, end = nearest(-0.05), nearest(0.0), nearest(0.5)
    # A degenerate grid can give a numerical zero for every AUC. Reject it explicitly.
    require(start <= zero < end, "time grid does not resolve the 0–0.5 s AUC window")
    return times, start, zero, end


def auc_of_mean(matrix, indices, *, scale=1.0):
    """Drop column 1, mean trials with missing omission, minimum baseline, trapz."""
    width = len(matrix[0])
    times, start, zero, end = time_axis(width - 1)
    trace = _trace(matrix, indices, width)[1:]
    trace = [x / scale if x is not None else None for x in trace]
    baseline_values = [x for x in trace[start:zero + 1] if x is not None]
    baseline = min(baseline_values) if baseline_values else None
    auc = None
    if baseline is not None and all(x is not None for x in trace[zero:end + 1]):
        auc = sum((times[j + 1] - times[j]) *
                  ((trace[j] - baseline) + (trace[j + 1] - baseline)) / 2.0
                  for j in range(zero, end))
    return {
        "auc": auc, "n_trials": len(indices), "baseline_min": baseline,
        "window_sample_indices_zero_based": {"baseline_start": start, "zero": zero, "auc_end": end},
        "effective_time_seconds": {"baseline_start": times[start], "zero": times[zero], "auc_end": times[end]},
    }


def validate_population(population, declared, where):
    require(isinstance(population, dict), f"{where}: rat-keyed object required")
    require(set(population) == set(declared), f"{where}: observed rat keys must exactly equal declared full roster")
    result = {}
    for rat in declared:
        data = population[rat]
        require(isinstance(data, dict), f"{where}/{rat}: object required")
        matrix, behavior = data.get("cpin"), data.get("behavior")
        require(isinstance(matrix, list) and matrix, f"{where}/{rat}: nonempty CPIn matrix required")
        require(isinstance(behavior, list) and len(matrix) == len(behavior), f"{where}/{rat}: photometry/behavior row mismatch")
        require(isinstance(matrix[0], list), f"{where}/{rat}: CPIn rows must be arrays")
        width = len(matrix[0])
        time_axis(width - 1)
        clean_matrix, clean_behavior, identities = [], [], set()
        for i, (row, b) in enumerate(zip(matrix, behavior)):
            loc = f"{where}/{rat}/row{i}"
            require(isinstance(row, list) and len(row) == width, f"{loc}: ragged CPIn matrix")
            clean_matrix.append([number(x, loc, nullable=True) for x in row])
            require(isinstance(b, dict), f"{loc}: behavior record required")
            require(isinstance(b.get("trial_id"), str) and b["trial_id"], f"{loc}: explicit trial_id required")
            require(isinstance(b.get("unique_day"), str) and len(b["unique_day"]) == 8, f"{loc}: UniqueDay must be YYYYMMDD")
            unique_day = day(b["unique_day"], loc)
            identity = (unique_day, b["trial_id"])
            require(identity not in identities, f"{loc}: duplicate rat/day/trial identity")
            identities.add(identity)
            require(b.get("block") in (1, 2, 3) and not isinstance(b.get("block"), bool), f"{loc}: block must be 1, 2 or 3")
            ptt = number(b.get("prev_trial_type"), loc)
            require(ptt.is_integer(), f"{loc}: PrevTrialType must be integer")
            require(isinstance(b.get("stage"), str) and b["stage"], f"{loc}: a single stage label required")
            clean_behavior.append({**b, "unique_day": unique_day})
        result[rat] = {"cpin": clean_matrix, "behavior": clean_behavior}
    return result


def stage_contrasts(population, declared):
    """Figure2h numerical contrasts, without native signrank inference."""
    rows = []
    for rat in declared:
        matrix, behavior = population[rat]["cpin"], population[rat]["behavior"]
        stages = {}
        for stage in STAGES:
            blocks = {}
            for block, label in ((2, "high"), (3, "low")):
                ids = [i for i, b in enumerate(behavior) if b["stage"] == stage and b["block"] == block and b["prev_trial_type"] != 2]
                blocks[label] = auc_of_mean(matrix, ids)
                blocks[label]["included_trial_ids"] = [[behavior[i]["unique_day"], behavior[i]["trial_id"]] for i in ids]
            high, low = blocks["high"]["auc"], blocks["low"]["auc"]
            stages[stage] = {**blocks, "high_minus_low_auc": high - low if high is not None and low is not None else None}
        pro, di = (stages[s]["high_minus_low_auc"] for s in STAGES)
        effect = pro - di if pro is not None and di is not None else None
        rows.append({"rat": rat, "stages": stages, "proestrus_minus_diestrus": effect,
                     "status": "computable" if effect is not None else "incomplete_stage_or_signal"})
    valid = [r["proestrus_minus_diestrus"] for r in rows if r["proestrus_minus_diestrus"] is not None]
    return {"rats": rows, "n_declared_rats": len(declared), "n_computable_rats": len(valid),
            "mean_rat_effect_complete_cohort_only": mean(valid) if len(valid) == len(declared) else None,
            "inference": "No signrank p-value or empirical acceptance score is produced."}


def serum_contrasts(population, declared, serum_table):
    require("G127" in population, "Figure2 serum source requires G127 to define its common time axis")
    width = len(population["G127"]["cpin"][0])
    require(all(len(population[r]["cpin"][0]) == width for r in declared), "serum CPIn widths must match source G127 time axis")
    require(isinstance(serum_table, list), "serum_table must be an explicit array")
    serum, table_rows = {}, []
    for i, row in enumerate(serum_table):
        require(isinstance(row, dict), f"serum_table/{i}: object required")
        rat = row.get("rat")
        require(isinstance(rat, str) and rat, f"serum_table/{i}: rat required")
        date = day(row.get("session_date"), f"serum_table/{i}")
        key = (rat, date)
        require(key not in serum, f"serum_table/{i}: ambiguous duplicate rat/day serum join")
        concentration = number(row.get("estradiol_conc"), f"serum_table/{i}", nullable=True)
        serum[key] = concentration
        table_rows.append({"rat": rat, "unique_day": date, "estradiol_conc": concentration})
    sessions, normalization, observed_pairs = [], [], set()
    for rat in declared:
        matrix, behavior = population[rat]["cpin"], population[rat]["behavior"]
        mixed = [i for i, b in enumerate(behavior) if b["block"] == 1 and b["prev_trial_type"] != 2]
        mixed_mean = _trace(matrix, mixed, width)  # Deliberately includes leading column.
        finite = [x for x in mixed_mean if x is not None]
        divisor = max(finite) if finite else None
        require(divisor is not None and divisor != 0, f"{rat}: mixed-block normalization is undefined or zero")
        normalization.append({"rat": rat, "divisor": divisor, "n_mixed_trials": len(mixed), "leading_column_included": True})
        for date in sorted({b["unique_day"] for b in behavior}):
            key = (rat, date)
            observed_pairs.add(key)
            day_rows = [b for b in behavior if b["unique_day"] == date]
            labels = sorted({b["stage"] for b in day_rows})
            entry = {"rat": rat, "unique_day": date, "n_observed_trials": len(day_rows), "stage_labels": labels}
            if key not in serum:
                sessions.append({**entry, "status": "no_serum_sample", "delta_auc": None})
                continue
            require(len(labels) == 1, f"{rat}/{date}: source serum output requires an unambiguous single stage")
            entry.update({"stage": labels[0], "estradiol_conc": serum[key]})
            if key in LOW_SNR:
                sessions.append({**entry, "status": "source_excluded_low_snr", "delta_auc": None})
                continue
            blocks = {}
            for block, label in ((2, "high"), (3, "low")):
                ids = [i for i, b in enumerate(behavior) if b["unique_day"] == date and b["block"] == block and b["prev_trial_type"] != 2]
                blocks[label] = auc_of_mean(matrix, ids, scale=divisor)
                blocks[label]["included_trial_ids"] = [behavior[i]["trial_id"] for i in ids]
            high, low = blocks["high"]["auc"], blocks["low"]["auc"]
            delta = high - low if high is not None and low is not None else None
            sessions.append({**entry, **blocks, "delta_auc": delta,
                             "status": "source_included" if delta is not None else "source_filtered_missing_auc"})
    unmatched = [r for r in table_rows if (r["rat"], r["unique_day"]) not in observed_pairs]
    included = [s for s in sessions if s["status"] == "source_included"]
    delta = [s["delta_auc"] for s in included]
    hormones = [s["estradiol_conc"] for s in included]
    return {"normalization": normalization, "session_ledger": sessions, "unmatched_serum_rows": unmatched,
            "source_shaped_arrays": {"delta_good": delta,
                                         "E2_good": hormones,
                                         "stages": [s["stage"] for s in included]},
            "pearson_r": pearson_complete_vectors(hormones, delta),
            "pearson_inference": "Descriptive source correlation only; no p-value, independence claim or grouped improvement score.",
            "n_joined_source_included_sessions": len(included),
            "n_joined_source_included_rats": len({s["rat"] for s in included}),
            "published_panel_population_for_audit_only": {"rats": 5, "sessions": 41,
                "meaning": "Published Figure2i plotted population, not a filter or an observed archive inventory."}}


def cohort_audit(regular, serum, manifest):
    require(isinstance(manifest, dict), "figure3_manifest object required; it is not an empirical validation")
    rats = roster(manifest.get("ratlist"), "figure3_manifest/ratlist")
    require(rats == list(FIGURE3_RATS), "Figure3 roster must equal the pinned nine-rat source list, in order")
    require(manifest.get("best_fits_supplied") is True, "Figure3 must retain supplied BestFits, not silently substitute refitting")
    sessions = manifest.get("sessions")
    require(isinstance(sessions, list), "Figure3 explicit session inventory required (empty means unknown)")
    pairs = set()
    for i, row in enumerate(sessions):
        require(isinstance(row, dict) and row.get("rat") in rats, f"figure3_manifest/sessions/{i}: rat outside declared roster")
        date = day(row.get("unique_day"), f"figure3_manifest/sessions/{i}")
        key = (row["rat"], date)
        require(key not in pairs, "Figure3 duplicate rat/day inventory entry")
        pairs.add(key)
    rows = []
    for rat in sorted(set(regular) | set(serum) | set(rats)):
        regular_days = sorted({b["unique_day"] for b in regular.get(rat, {}).get("behavior", [])})
        serum_days = sorted({b["unique_day"] for b in serum.get(rat, {}).get("behavior", [])})
        fig3_days = sorted(d for r, d in pairs if r == rat)
        rows.append({"rat": rat, "figure2_days": regular_days, "figure2_serum_days": serum_days,
                     "figure3_declared_rat": rat in rats, "figure3_inventory_days": fig3_days,
                     "all_three_observed_day_intersection": sorted(set(regular_days) & set(serum_days) & set(fig3_days))})
    return {"rat_session_map": rows, "figure3_missing_session_inventory_rats": [r for r in rats if not any(k[0] == r for k in pairs)],
            "cohort_selection": "No rat or session is selected by intersection; inventories are reported, not qualified.",
            "native_join_verified": False}


def evaluate(payload):
    require(isinstance(payload, dict) and payload.get("schema_version") == 1, "input schema_version must be 1")
    require(payload.get("input_kind") in ("generated_engineering_control", "authorized_native_export"), "explicit input_kind required")
    regular_roster = roster(payload.get("figure2_ratlist"), "figure2_ratlist")
    serum_roster = roster(payload.get("figure2_serum_ratlist"), "figure2_serum_ratlist")
    regular = validate_population(payload.get("figure2"), regular_roster, "figure2")
    serum = validate_population(payload.get("figure2_serum"), serum_roster, "figure2_serum")
    stage_result = stage_contrasts(regular, regular_roster)
    serum_result = serum_contrasts(serum, serum_roster, payload.get("serum_table"))
    singleton_selections = []
    for rat in stage_result["rats"]:
        for stage, blocks in rat["stages"].items():
            for block in ("high", "low"):
                if blocks[block]["n_trials"] == 1:
                    singleton_selections.append({"component": "stage", "rat": rat["rat"], "stage": stage, "block": block})
    for rat in serum_result["normalization"]:
        if rat["n_mixed_trials"] == 1:
            singleton_selections.append({"component": "serum_normalization", "rat": rat["rat"]})
    for session in serum_result["session_ledger"]:
        for block in ("high", "low"):
            if block in session and session[block]["n_trials"] == 1:
                singleton_selections.append({"component": "serum_auc", "rat": session["rat"], "unique_day": session["unique_day"], "block": block})
    return {"schema_version": 1, "task_id": TASK_ID, "implementation": "initial-evaluator-v1",
            "input_kind": payload["input_kind"], "source_commit": SOURCE_COMMIT,
            "status": "construction_component_only", "research_qualified": False, "binary_reward_registered": False,
            "prospective_export_policy": "Mean always follows the declared trial axis, including singleton trial groups; MATLAB default-dimension singleton behavior is not reproduced or empirically qualified.",
            "singleton_selections_affected_by_export_policy": singleton_selections,
            "figure2h_stage_contrasts": stage_result,
            "figure2i_serum_contrasts": serum_result,
            "cross_archive_audit": cohort_audit(regular, serum, payload.get("figure3_manifest")),
            "preserved_holds": HOLDS}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="explicit native-shaped JSON export or generated control")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        # reject JSON NaN/Infinity rather than letting Python silently accept them
        payload = json.loads(args.input.read_text(), object_pairs_hook=unique_object,
                             parse_constant=lambda x: (_ for _ in ()).throw(ContractError(f"invalid JSON constant {x}")))
        result = evaluate(payload)
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"input rejected: {exc}\n")
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
