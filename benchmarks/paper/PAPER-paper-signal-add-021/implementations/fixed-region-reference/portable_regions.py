"""Full15 paired EEG region reference; stdlib, no MATLAB or native imports.

Consumes a separately accepted, authenticated full projection. This is a
benchmark-defined region analysis, not FieldTrip cluster-output parity.
"""
from __future__ import annotations
import argparse
import array
import hashlib
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

BEHAVIOR_PIN = (14692, "f3c724074660dda8f692831eecd6082fd4c7e1750714aa3e3fb8d15a7d4d9109")
VERIFIER_PIN = (20338, "c98bdf711e9245202c5f4cbd498e5bc22f65b0387d31367650a4ab8e453b201d")
CONTRACT_SHA = "6a56734ba3c2a2cda072e6bb1da73507a32d4e699de3098efc362db1771eab52"
CONDITIONS = ("NT.pin.all", "NT.pout.all", "T.pin.all", "T.pout.all")
ROSTER = (1, 3, 5, 6, 7, 10, 12, 14, 15, 17, 22, 23, 25, 26, 27)
ROI6 = ("O1", "PO7", "PO3", "P1", "P3", "P5")
ROI7 = ROI6 + ("P7",)
BANDS = (("alpha", 8, 12), ("beta", 13, 30))
WINDOWS = (("early", 0.5, 1.5), ("late", 3, 4), ("extended_late", 3, 4.5))
EFFECTS = ("pin_T_minus_NT", "pout_T_minus_NT", "location_interaction")


def pinned_module(path, pin, name):
    path = Path(path)
    body = path.read_bytes()
    if (len(body), hashlib.sha256(body).hexdigest()) != pin:
        raise ValueError("wrong immutable source: " + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def regions(labels, frequencies, times):
    if len(labels) != 7 or set(labels) != set(ROI7):
        raise ValueError("all seven unique aligned labels are required")
    for coordinates in (frequencies, times):
        if (not coordinates or any(type(x) not in (float, int) or not math.isfinite(x) for x in coordinates)
                or any(a >= b for a, b in zip(coordinates, coordinates[1:]))):
            raise ValueError("finite strictly increasing axes required")
    result = []
    for roi_name, roi in (("primary6", ROI6), ("sensitivity7", ROI7)):
        ci = [i for i, label in enumerate(labels) if label in roi]
        for band, lo, hi in BANDS:
            fi = [i for i, x in enumerate(frequencies) if lo <= x <= hi]
            for window, start, stop in WINDOWS:
                ti = [i for i, x in enumerate(times) if start <= x <= stop]
                if not fi or not ti:
                    raise ValueError("empty declared band/window; no nearest-bin substitution")
                result.append({"id": "/".join((roi_name, band, window)),
                               "roi": roi_name, "channels": list(roi), "band": band,
                               "frequency_bounds": [lo, hi], "window": window,
                               "time_bounds": [start, stop], "channel_indices": ci,
                               "frequency_indices": fi, "time_indices": ti})
    return result


def reduce_regions(values, labels, frequencies, times):
    """Four conditions in C[condition,channel,frequency,time,position], all15.

    Every selected value must be finite; missing unselected bins do not alter
    these region statistics. Means use fsum, then linear paired contrasts.
    Floating operation order differs from MATLAB mean(T-NT), explicitly.
    """
    specs = regions(labels, frequencies, times)
    nf, nt, people = len(frequencies), len(times), 15
    if len(values) != 4 * 7 * nf * nt * people:
        raise ValueError("complete four-condition full15 tensor required")
    output = []
    for spec in specs:
        offsets = [((c * nf + f) * nt + t) * people
                   for c in spec["channel_indices"] for f in spec["frequency_indices"]
                   for t in spec["time_indices"]]
        means = []
        for condition in range(4):
            base = condition * 7 * nf * nt * people
            group = []
            for person in range(people):
                def selected():
                    for offset in offsets:
                        value = values[base + offset + person]
                        if not math.isfinite(value):
                            raise ValueError("nonfinite selected bin; no participant/bin omission or imputation")
                        yield value
                group.append(math.fsum(selected()) / len(offsets))
            means.append(group)
        pin = [a - b for a, b in zip(means[2], means[0])]
        pout = [a - b for a, b in zip(means[3], means[1])]
        output.append({**spec, "bins_per_condition_person": len(offsets),
                       "condition_means_by_source_position": means,
                       "effects": {EFFECTS[0]: pin, EFFECTS[1]: pout,
                                   EFFECTS[2]: [a - b for a, b in zip(pin, pout)]}})
    return output


def infer_regions(reduced, behavior, *, bootstrap_draws=2000):
    expected = {"/".join((r, b[0], w[0])) for r in ("primary6", "sensitivity7")
                for b in BANDS for w in WINDOWS}
    if len(reduced) != 12 or {r["id"] for r in reduced} != expected:
        raise ValueError("all twelve declared region definitions required")
    records, pvalues = [], {}
    for region in reduced:
        if set(region["effects"]) != set(EFFECTS):
            raise ValueError("all three location effects required")
        entry = {k: v for k, v in region.items() if k != "effects"}
        entry["effects"] = {}
        for effect in EFFECTS:
            differences = region["effects"][effect]
            if len(differences) != 15 or any(not math.isfinite(x) for x in differences):
                raise ValueError("all fifteen finite paired positions required")
            flip = behavior.exact_sign_flip(differences)
            entry["effects"][effect] = {
                "differences_by_source_position": differences,
                "paired": behavior.paired_summary(differences), "sign_flip": flip,
                "bootstrap": behavior.bootstrap_interval(differences, seed=20261114, draws=bootstrap_draws),
                "leave_one_position_out": [
                    {"excluded_position": i, "source_declared_id_assumption": ROSTER[i],
                     "paired": behavior.paired_summary(differences[:i] + differences[i+1:])}
                    for i in range(15)]}
            pvalues[region["id"] + "/" + effect] = flip["p_two_sided"]
        records.append(entry)
    adjusted = behavior.holm(pvalues)
    for region in records:
        for effect in EFFECTS:
            region["effects"][effect]["holm_all36_region_sensitivity_p"] = adjusted[region["id"] + "/" + effect]
    return {"schema": "tms-paired-eeg-region-reference-v1", "source_positions": list(range(15)),
            "source_declared_roster_assumption": list(ROSTER), "regions": records,
            "region_definitions": 12, "paired_effects": 36, "leave_one_out_summaries": 540,
            "multiple_comparison_family": "All36 fixed region/effect sensitivity comparisons; separate from the primary cluster test.",
            "bin_policy": "Inclusive coordinate inequalities; no nearest-bin snapping for these benchmark regions.",
            "units": "Released dB power; equal-weight selected channel/frequency/time mean per source position.",
            "pairing_assumption": "Allfour released conditions retain the source-declared joint15 order; physical ID map is not independently certified.",
            "fieldtrip_numeric_parity_qualified": False, "cluster_test_performed": False,
            "full_registered_task_qualified": False}


def load_projection(root, manifest_bytes, manifest_sha, verifier):
    """Reuse the accepted acquisition owner's ordinary authenticated byte reader.

    A full producer/owner/peer projection review must precede actual selection.
    This reader consumes its selected INPUT pin; it does not replace that review.
    """
    root = Path(root)
    verifier.DEADLINE = time.monotonic() + 120
    verifier.READS = 0
    raw, _ = verifier.ordinary(root / "INPUT.json", 262144,
                              {"bytes": manifest_bytes, "sha256": manifest_sha})
    meta = verifier.decode(raw)
    if (meta["schema"] != "tms-full-paired-original-input-v1" or meta["shape"] != [4,7,53,200,15]
            or meta["conditions"] != list(CONDITIONS) or meta["source_positions"] != list(range(15))
            or meta["source_declared_roster"] != list(ROSTER)
            or meta["scientific_contract"]["sha256"] != CONTRACT_SHA
            or meta["dtype"] != "little-endian-IEEE754-binary64"
            or meta["order"] != "C; source_position fastest" or meta["values"]["file"] != "values.f64"
            or meta["values"]["bytes"] != 35616000
            or len(meta["frequency_coordinates"]) != 53 or len(meta["time_coordinates"]) != 200):
        raise ValueError("wrong accepted full scientific projection geometry")
    regions(meta["selected_labels"], meta["frequency_coordinates"], meta["time_coordinates"])
    raw, _ = verifier.ordinary(root / "values.f64", 35616000,
                              {k: meta["values"][k] for k in ("bytes", "sha256")})
    values = array.array("d")
    if values.itemsize != 8:
        raise ValueError("binary64 array runtime required")
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    return meta, values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--manifest-bytes", required=True, type=int)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--projection-verifier", required=True, type=Path)
    parser.add_argument("--behavior-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    verifier = pinned_module(args.projection_verifier, VERIFIER_PIN, "accepted_projection_verifier")
    behavior = pinned_module(args.behavior_source, BEHAVIOR_PIN, "accepted_behavior_statistics")
    meta, values = load_projection(args.input_root, args.manifest_bytes, args.manifest_sha256, verifier)
    result = infer_regions(reduce_regions(values, meta["selected_labels"],
                           meta["frequency_coordinates"], meta["time_coordinates"]), behavior)
    result["input_manifest"] = {"bytes": args.manifest_bytes, "sha256": args.manifest_sha256}
    result["projection_values"] = meta["values"]
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
