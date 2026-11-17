"""Collect the selected sentence-only Figure 4 result from actual author scores.

The full original prediction support is mandatory. Unrecovered display/group
definitions remain unavailable rather than being replaced with convenient ones.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from custody import TASK_ID, finite, loads, read_bounded, require, write_json_exclusive


def ranked_group(rows, top_k=10):
    """Source-defined peak-CV selection; never choose on held-out performance."""
    require(type(top_k) is int and top_k > 0, "positive group selection count required")
    require(len(rows) >= top_k, "insufficient complete eligible group members")
    peaks = [max(row["cv_curve"]) for row in rows]
    ranked = sorted(range(len(rows)), key=lambda index: -peaks[index])
    cutoff = peaks[ranked[top_k - 1]]
    above = [index for index in ranked if peaks[index] > cutoff]
    at = [index for index in ranked if peaks[index] == cutoff]
    if len(above) + len(at) > top_k:
        return {"status": "unavailable_cutoff_tie_rule", "cutoff_cv": cutoff,
                "above_cutoff": [rows[index]["identity"] for index in above],
                "at_cutoff": [rows[index]["identity"] for index in at],
                "selected": None, "mean_test_curve": None}
    selected = [rows[index] for index in ranked[:top_k]]
    width = len(selected[0]["test_curve"])
    require(all(len(row["test_curve"]) == width for row in selected), "group window coverage differs")
    return {"status": "selected_from_peak_training_cv", "cutoff_cv": cutoff,
            "selected": [{"identity": row["identity"], "test_curve": row["test_curve"],
                          "cv_curve": row["cv_curve"]} for row in selected],
            "mean_test_curve": [math.fsum(row["test_curve"][index] for row in selected) / top_k
                                for index in range(width)],
            "display_interval": None, "display_interval_status": "original_95_percent_formula_unrecovered"}


def collect(manifest, scores, windows, group_map=None):
    require(manifest.get("schema") == "treebank-figure4-preparation/v2" and manifest.get("task_id") == TASK_ID,
            "wrong preparation schema/task")
    require(isinstance(windows, list) and windows, "actual source window manifest required")
    keys = [row["source_key"] for row in windows]
    require(all(isinstance(key, str) and key for key in keys) and len(set(keys)) == len(keys),
            "unique source window keys required")
    require(isinstance(scores, dict) and set(scores) == set(manifest["eligibility"]), "complete source subjects required")
    require(isinstance(manifest.get("subjects"), list), "prepared subject rows required")
    subject_ids = [row.get("subject") for row in manifest["subjects"]]
    require(len(subject_ids) == len(set(subject_ids)) and set(subject_ids) == set(manifest["eligibility"]),
            "prepared subject rows differ from declared subject support")
    contacts, map_points, map_omissions, all_dk = [], [], [], set()
    for subject in manifest["subjects"]:
        sid = subject["subject"]
        expected = manifest["eligibility"][sid]
        require(isinstance(scores[sid], dict) and set(scores[sid]) == set(expected),
                f"complete eligible contact support required: {sid}")
        by_contact = {row["contact"]: row for row in subject["contacts"]}
        require(len(by_contact) == len(subject["contacts"]), "duplicate prepared contact")
        require(expected == [row["contact"] for row in subject["contacts"] if not row["excluded"]],
                "eligibility differs from ordered metadata")
        for name in expected:
            values = scores[sid][name]
            require(isinstance(values, dict) and set(values) == set(keys), f"complete window support required: {sid}/{name}")
            test, cv = [], []
            for key in keys:
                require(isinstance(values[key], dict) and set(values[key]) == {"test_score", "cv_score"},
                        "actual two-field source score object required")
                a, b = finite(values[key]["test_score"], "held-out ROC-AUC"), finite(values[key]["cv_score"], "training CV ROC-AUC")
                require(0 <= a <= 1 and 0 <= b <= 1, "ROC-AUC outside [0,1]")
                test.append(a)
                cv.append(b)
            metadata = by_contact[name]
            record = {"identity": [sid, name], "label_index": metadata["label_index"],
                      "test_curve": test, "cv_curve": cv,
                      "held_out_peak": max(test), "training_cv_peak": max(cv),
                      "all_held_out_peak_windows": [keys[index] for index, value in enumerate(test) if value == max(test)],
                      "desikan_killiany": (metadata.get("anatomy") or {}).get("DesikanKilliany")}
            if record["desikan_killiany"]:
                all_dk.add(record["desikan_killiany"])
            contacts.append(record)
            coordinates = metadata.get("released_coordinates")
            if sid == "sub_5":
                map_omissions.append({"identity": [sid, name], "reason": "source_subject5_map_exclusion_only"})
            elif coordinates is None:
                map_omissions.append({"identity": [sid, name], "reason": "no_released_aggregate_coordinate_row"})
            else:
                map_points.append({"identity": [sid, name], "held_out_peak": max(test),
                                   "released_coordinate_fields": coordinates})
    example = [row for row in contacts if row["identity"] == ["sub_10", "T1cIf8"]]
    require(len(example) == 1 and example[0]["label_index"] == 37, "complete published example contact required")
    groups = {"status": "unavailable_original_dk_to_lobe_definition", "results": None,
              "observed_dk_labels": sorted(all_dk)}
    if group_map is not None:
        require(isinstance(group_map, dict) and set(group_map) == {"mapping", "source_provenance"}, "explicit group map and provenance required")
        mapping = group_map["mapping"]
        require(isinstance(mapping, dict) and set(mapping) == all_dk, "complete observed DK taxonomy mapping required")
        require(all(value in ("Temporal", "Frontal", "outside") for value in mapping.values()), "unknown lobe assignment")
        groups = {"status": "owner_supplied_mapping_calculation_not_original_mapping_authentication",
                  "source_provenance": group_map["source_provenance"],
                  "results": {name: ranked_group([row for row in contacts if row["identity"][0] != "sub_5" and
                                                   mapping.get(row["desikan_killiany"]) == name])
                              for name in ("Temporal", "Frontal")}}
    return {
        "schema": "treebank-original-figure4-components/v2", "task_id": TASK_ID,
        "selected_primary": "complete_original_figure4a_b_c_sentence_onset_no_speech",
        "source_windows": windows,
        "supplied_prediction_support": {"contacts": len(contacts), "curves": contacts,
                                        "coverage": "complete_for_supplied_manifest_and_window_table_only",
                                        "original_support_authentication": "not_performed_by_this_pure_reducer"},
        "panel_a": {"all_contact_peaks_computed": True, "released_coordinate_join": map_points,
                    "map_only_omissions": map_omissions, "projection_status": "original_nearest_pial_fsaverage_projection_not_verified",
                    "published_plot_parity": "unavailable"},
        "panel_b": {"example": example[0], "window_axis": "actual_source_nominal_keys",
                    "published_display_convention": "unresolved"},
        "panel_c": groups,
        "full_primary_reproduction": "unavailable",
        "scientific_limits": ["Standalone reduction does not authenticate the supplied manifest or window table; the native producer rederives metadata and observes its actual source grid.",
                              "Complete map projection, source group membership/tie/display definitions require qualification.",
                              "Source unstratified test split and terminal window lengths are not silently changed.",
                              "Current metadata support does not prove identical historical preparation or seizure exclusions.",
                              "No reference agreement, candidate improvement or benchmark readiness is established here."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared", "scores", "windows", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--group-map", type=Path)
    args = parser.parse_args()
    result = collect(loads(read_bounded(args.prepared, 16 * 1024 * 1024)),
                     loads(read_bounded(args.scores, 32 * 1024 * 1024)),
                     loads(read_bounded(args.windows, 65536)),
                     loads(read_bounded(args.group_map, 65536)) if args.group_map else None)
    write_json_exclusive(args.output, result)


if __name__ == "__main__":
    main()
