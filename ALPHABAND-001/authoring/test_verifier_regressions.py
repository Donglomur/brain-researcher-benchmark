"""Verifier regressions using retained oracle outputs when REPAIR_ORACLE_OUTPUT is set.

The default fixtures are reference-backed numbers, not independent EEG recomputations.
Mutating real outputs tests verifier behavior; it does not establish scientific validity.
"""
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]


def _base_outputs():
    oracle_output = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if oracle_output:
        source = Path(oracle_output)
        with (source / "per_subject.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            for key in ("ec_occipital_alpha", "eo_occipital_alpha", "ratio"):
                row[key] = float(row[key])
        result = json.loads((source / "alpha_ratio.json").read_text())
        metadata = json.loads((source / "run_metadata.json").read_text())
        return rows, result, metadata, (source / "findings.md").read_text()

    ref = np.load(TASK / "tests/reference.npz", allow_pickle=False)
    rows = [dict(subject=str(s), ec_occipital_alpha=float(ec), eo_occipital_alpha=float(eo), ratio=float(r))
            for s, ec, eo, r in zip(ref["ref_ids"], ref["ref_ec"], ref["ref_eo"], ref["ref_ratio"])]
    channels = ["O1", "Oz", "O2"]
    result = dict(occipital_alpha_ratio_ec_over_eo=float(ref["occ_mean"]), band_hz=[8, 13],
                  n_subjects=5, channels=channels, wholehead_alpha_ratio_for_reference=float(ref["wholehead_mean"]))
    metadata = dict(dataset_id="eegbci", dataset_version="1.0.0", subjects=[1, 2, 3, 4, 5],
                    runs={"eyes_open": 1, "eyes_closed": 2}, band_hz=[8, 13],
                    channels=channels, psd_method="Welch", reference="common average",
                    power_units="V^2/Hz", aggregation="mean_of_subject_ratios",
                    welch=dict(segment_sec=2, n_fft=320, n_overlap=0, window="hamming",
                               remove_dc=True, average="mean"))
    findings = "Occipital alpha is enhanced with eyes closed in this modern sample."
    return rows, result, metadata, findings


POSITIVE_CASES = {"reference", "reversed_subjects", "rounded_measurements", "equivalent_metadata_and_findings"}
CASES = [
    "reference", "reversed_subjects", "rounded_measurements", "equivalent_metadata_and_findings",
    "empty_rows", "missing_subject", "extra_subject", "duplicate",
    "invalid_power", "shared_power_scale", "swapped_conditions", "one_bad_subject",
    "nonfinite", "fabricated_right_group_mean", "pooled_group_aggregation",
    "headline_disagreement", "ratio_identity", "wrong_wholehead", "wrong_channels",
    "wrong_segment", "wrong_units", "wrong_aggregation", "wrong_dataset_version",
    "missing_alpha_ratio.json", "missing_per_subject.csv", "missing_run_metadata.json",
    "missing_findings.md", "empty_findings",
]


@pytest.mark.parametrize("case", CASES)
def test_contract(tmp_path, case):
    rows, result, metadata, findings = _base_outputs()
    headline = result["occipital_alpha_ratio_ec_over_eo"]
    if case == "empty_rows":
        rows = []
    elif case == "missing_subject":
        rows.pop()
    elif case == "extra_subject":
        rows.append({**rows[0], "subject": "6"})
    elif case == "duplicate":
        rows.append(rows[0].copy())
    elif case == "invalid_power":
        rows[0]["ec_occipital_alpha"] = -1
        rows[0]["eo_occipital_alpha"] = 0
    elif case == "shared_power_scale":
        for row in rows:
            row["ec_occipital_alpha"] *= 1.25
            row["eo_occipital_alpha"] *= 1.25
    elif case == "swapped_conditions":
        for row in rows:
            row["ec_occipital_alpha"], row["eo_occipital_alpha"] = (
                row["eo_occipital_alpha"], row["ec_occipital_alpha"])
            row["ratio"] = row["ec_occipital_alpha"] / row["eo_occipital_alpha"]
        headline = float(np.mean([row["ratio"] for row in rows]))
    elif case == "one_bad_subject":
        rows[0]["ec_occipital_alpha"] *= 1.29
        rows[0]["eo_occipital_alpha"] *= 0.71
        rows[0]["ratio"] = rows[0]["ec_occipital_alpha"] / rows[0]["eo_occipital_alpha"]
        headline = float(np.mean([row["ratio"] for row in rows]))
    elif case == "nonfinite":
        rows[0]["ec_occipital_alpha"] = float("nan")
        rows[0]["ratio"] = float("nan")
    elif case == "fabricated_right_group_mean":
        # Nonconstant fabricated rows preserve the real group ratio and internal EC/EO
        # identities; per-subject source measurements must still reject them.
        for row, ratio in zip(rows, np.linspace(headline - 2, headline + 2, len(rows))):
            row["eo_occipital_alpha"] = 1e-11
            row["ec_occipital_alpha"] = float(ratio) * row["eo_occipital_alpha"]
            row["ratio"] = float(ratio)
    elif case == "pooled_group_aggregation":
        # Leave the metadata label untouched: the numerical gate, not just metadata,
        # must reject replacing the mean of ratios with a ratio of pooled powers.
        headline = sum(row["ec_occipital_alpha"] for row in rows) / sum(
            row["eo_occipital_alpha"] for row in rows)
    elif case == "headline_disagreement":
        headline += 2.9
    elif case == "ratio_identity":
        # The ratio remains close to its reference, but no longer equals the submitted powers.
        rows[0]["ratio"] += 0.1
    elif case == "rounded_measurements":
        # Six significant digits for powers and three decimals for ratios are sufficient
        # to report these measurements; exact floating-point strings are not required.
        for row in rows:
            row["ec_occipital_alpha"] = float(f"{row['ec_occipital_alpha']:.6g}")
            row["eo_occipital_alpha"] = float(f"{row['eo_occipital_alpha']:.6g}")
            row["ratio"] = round(row["ratio"], 3)
        headline = round(headline, 3)

    if case == "reversed_subjects":
        rows.reverse()
        metadata["subjects"].reverse()
    elif case == "equivalent_metadata_and_findings":
        for row in rows:
            row["subject"] = f"S{int(row['subject']):03d}"
        metadata["subjects"] = [f"S{int(subject):03d}" for subject in metadata["subjects"]]
        metadata["dataset_id"] = "EEGMMIDB"
        metadata["reference"] = "CAR"
        result["channels"] = metadata["channels"] = ["O1", "OZ", "O2"]
        metadata["power_units"] = "V²/Hz"
        metadata["welch"]["window"] = "periodic Hamming"
        findings = (
            f"Across O1/Oz/O2, EC alpha density exceeded EO in all five participants. "
            f"The mean within-participant EC/EO ratio was {headline:.3f}; this modern "
            "descriptive contrast is not the original historical cohort or a population estimate."
        )
    elif case == "empty_findings":
        findings = " \n\t"
    with (tmp_path / "per_subject.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["subject", "ec_occipital_alpha", "eo_occipital_alpha", "ratio"])
        writer.writeheader()
        writer.writerows(rows)
    result["occipital_alpha_ratio_ec_over_eo"] = headline
    if case == "wrong_channels":
        result["channels"] = metadata["channels"] = ["F1", "F2", "Fz"]
    if case == "wrong_wholehead":
        result["wholehead_alpha_ratio_for_reference"] = headline
    elif case == "wrong_segment":
        metadata["welch"]["segment_sec"] = 128
        metadata["welch"]["n_fft"] = 20480
    elif case == "wrong_units":
        metadata["power_units"] = "uV^2/Hz"
    elif case == "wrong_aggregation":
        metadata["aggregation"] = "ratio_of_group_mean_powers"
    elif case == "wrong_dataset_version":
        metadata["dataset_version"] = "2.0.0"
    (tmp_path / "alpha_ratio.json").write_text(json.dumps(result))
    (tmp_path / "run_metadata.json").write_text(json.dumps(metadata))
    (tmp_path / "findings.md").write_text(findings)
    if case.startswith("missing_") and case[len("missing_"):] in {
            "alpha_ratio.json", "per_subject.csv", "run_metadata.json", "findings.md"}:
        (tmp_path / case[len("missing_"):]).unlink()
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", str(TASK / "tests/test_outputs.py")],
                          env={**os.environ, "OUTPUT_DIR": str(tmp_path)}, capture_output=True,
                          text=True, timeout=60)
    assert (proc.returncode == 0) == (case in POSITIVE_CASES), proc.stdout + proc.stderr
