"""Small generated engineering fixture; not BrainTreebank data or a model baseline."""
import argparse
import json
from pathlib import Path
import evaluator as ev

def make_plan():
    plan = {"schema_version": 1, "profile": ev.PROFILE, "source_revision": ev.REVISION,
            "endpoint": "rms", "support_units": "seconds",
            "shared_resources": {k: ev.canonical_sha("GENERATED_CONTROL_" + k) for k in ev.RESOURCE_KEYS},
            "population_manifest_sha256": ev.canonical_sha("GENERATED_CONTROL_ROSTER"),
            "saved_split_file_sha256": ev.canonical_sha("GENERATED_CONTROL_SPLIT"),
            "pretraining_exposure_manifest_sha256": ev.canonical_sha("NO_PRETRAINING_GENERATED_CONTROL"),
            "words": [], "channel_rankings": {}}
    for subject in sorted(ev.TRIALS):
        rows = []
        for i in range(48):
            row = {"id": f"{subject}_word{i:03d}", "subject": subject, "trial": ev.TRIALS[subject],
                   "movie": ev.MOVIES[subject], "start_s": i * 120.0, "end_s": i * 120.0 + 5.0,
                   "split": ("train", "validation", "test")[i % 3], "rms": float(i + 1)}
            rows.append(row)
        plan["words"].extend(rows)
        labels = ev.rms_quartile_labels(rows)
        plan["channel_rankings"][subject] = {
            "channels": [f"GENERATED_ELECTRODE_{i:03d}" for i in range(90)],
            "selection_rule": "training_only_linear_decodability",
            "feature_channel_order": [f"GENERATED_ELECTRODE_{i:03d}" for i in range(90)],
            "channel_order_evidence_sha256": ev.canonical_sha("GENERATED_CHANNEL_ORDER_" + subject),
            "ranking_evidence_sha256": ev.canonical_sha("GENERATED_RANKING_" + subject),
            "eligibility_evidence_sha256": ev.canonical_sha("GENERATED_ELIGIBILITY_" + subject),
            "fit_word_ids": [r["id"] for r in rows if r["split"] == "train" and labels[r["id"]] is not None]}
    return plan

def make_predictions(reference, arm):
    result = {"reference_sha256": reference["reference_sha256"], "arm": arm,
              "method": "pretrained_popt" if arm == "candidate" else "linear_concatenation",
              "shared_resources": reference["shared_resources"],
              "saved_split_file_sha256": reference["saved_split_file_sha256"],
              "pretraining_exposure_manifest_sha256": reference["pretraining_exposure_manifest_sha256"],
              "model_artifact_sha256": ev.canonical_sha("NO_MODEL_GENERATED_CONTROL_" + arm),
              "selection_split": "validation", "probability_semantics": "canonical_high_rms",
              "native_high_rms_index": {s: {str(c): 1 for c in ev.COUNTS} for s in ev.TRIALS}, "predictions": []}
    for ensemble in reference["ensembles"]:
        for row in reference["words"]:
            if row["subject"] != ensemble["subject"] or row["split"] != "test" or row["label_high_rms"] is None:
                continue
            p = (0.9 if row["label_high_rms"] else 0.1) if arm == "candidate" else 0.5
            result["predictions"].append({"word_id": row["id"], "electrode_count": ensemble["electrode_count"],
                                          "channels": ensemble["channels"], "probability_high_rms": p})
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory")
    args = parser.parse_args()
    out = Path(args.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    plan = make_plan()
    reference = ev.freeze(plan)
    artifacts = {"generated-plan.json": plan, "generated-reference.json": reference,
                 "generated-candidate.json": make_predictions(reference, "candidate"),
                 "generated-baseline.json": make_predictions(reference, "baseline")}
    for name, value in artifacts.items():
        (out / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")

if __name__ == "__main__":
    main()
