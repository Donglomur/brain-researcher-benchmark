"""Independent implementation of the Brain Treebank word-response kernel.

This consumes aligned, processed epochs. It does not load native recordings or
establish historical reproduction, linguistic specificity, or qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import t as student_t

TASK_ID = "PAPER-paper-method-replacement-011"
SOURCE_REVISION = "c54ba38eab7814538bc03b1b6d29a3f50f034e12"
SAMPLE_RATE = 2048
# Decimal endpoints converted to sample offsets by truncation toward zero.
# (pre start, pre end, post start, post end), half-open, relative to word onset.
WINDOWS = ((-1024, -819, 1024, 1228), (-819, -614, 1228, 1433),
           (-614, -409, 1433, 1638), (-409, -204, 1638, 1843),
           (-204, 0, 1843, 2048))
SOURCE_RUNS = {
    "sub_1": ("trial000", "trial001", "trial002"),
    "sub_2": tuple(f"trial{i:03d}" for i in range(7)),
    "sub_3": ("trial000", "trial001", "trial002"),
    "sub_4": ("trial000", "trial001", "trial002"),
    "sub_5": ("trial000",), "sub_6": ("trial000", "trial001", "trial004"),
    "sub_7": ("trial000", "trial001"), "sub_8": ("trial000",),
    "sub_9": ("trial000",), "sub_10": ("trial000", "trial001"),
}
HOLDS = [
    "Native HDF5, notch processing, alignment, timing and electrode exclusions are not independently validated.",
    "Declared inventory completeness does not verify authentic full-population membership or word inclusion.",
    "Word-level paired t statistics assume independent paired differences; overlapping words and temporal dependence remain unresolved.",
    "The global five-window Bonferroni family is prospective; exact published correction and numeric reference remain unqualified.",
    "Joint acoustic, visual, speaker and scene adjustment, sentence-position analysis and time-resolved decoding are not implemented here.",
    "Word responsiveness does not establish linguistic specificity or out-of-movie generalization.",
    "Train-only feature construction/electrode selection and protected participant/movie/temporal evaluation remain required.",
    "Stimulus/transcript rights, official-code reuse rights, candidate access parity and independent native reference remain open.",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def string_ids(value: Any, name: str) -> list[str]:
    require(isinstance(value, list) and bool(value), f"{name} must be a nonempty list")
    require(all(isinstance(x, str) and bool(x.strip()) for x in value), f"{name} must contain strings")
    require(len(set(value)) == len(value), f"{name} contains duplicates")
    return value


def fingerprint(value: Any, name: str) -> str:
    require(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
            f"{name} must be a lowercase sha256")
    return value


def window_means(epochs: np.ndarray, first_sample: int) -> tuple[np.ndarray, np.ndarray]:
    """Return E x W x 5 arrays without rounding times or truncating windows."""
    require(isinstance(first_sample, int) and not isinstance(first_sample, bool), "first_sample must be an integer")
    require(epochs.ndim == 3 and min(epochs.shape) > 0, "epochs must have shape electrodes,words,samples")
    require(np.issubdtype(epochs.dtype, np.number) and not np.iscomplexobj(epochs), "epochs must be real numeric values")
    require(np.isfinite(epochs).all(), "epochs contain non-finite values")
    pre, post = [], []
    for a, b, c, d in WINDOWS:
        require(a >= first_sample and d - first_sample <= epochs.shape[-1], "epochs do not cover all five complete window pairs")
        pre.append(epochs[..., a-first_sample:b-first_sample].mean(axis=-1, dtype=np.float64))
        post.append(epochs[..., c-first_sample:d-first_sample].mean(axis=-1, dtype=np.float64))
    pre, post = np.stack(pre, axis=-1), np.stack(post, axis=-1)
    require(np.isfinite(pre).all() and np.isfinite(post).all(), "window mean overflow")
    return pre, post


class PairedMoments:
    """Merge stable sufficient moments across runs without retaining word traces."""
    def __init__(self) -> None:
        self.n = 0
        self.mean = np.zeros(3)  # pre, post, paired difference
        self.m2 = np.zeros(3)

    def add(self, pre: np.ndarray, post: np.ndarray) -> None:
        pre, post = np.asarray(pre, dtype=np.float64), np.asarray(post, dtype=np.float64)
        require(pre.ndim == post.ndim == 1 and pre.shape == post.shape and pre.size > 0, "paired vectors must have equal nonzero length")
        require(np.isfinite(pre).all() and np.isfinite(post).all(), "paired vectors must be finite")
        values = np.stack((pre, post, pre-post))
        n = pre.size
        mean = values.mean(axis=1)
        m2 = np.sum((values - mean[:, None]) ** 2, axis=1)
        delta = mean - self.mean
        total = self.n + n
        self.m2 += m2 + delta * delta * self.n * n / total
        self.mean += delta * n / total
        require(np.isfinite(self.mean).all() and np.isfinite(self.m2).all(), "paired moment arithmetic overflow")
        self.n = total

    def result(self) -> dict[str, Any]:
        require(self.n >= 2, "paired test requires at least two words")
        variance = max(float(self.m2[2]), 0.0) / (self.n - 1)
        diff = float(self.mean[2])
        if variance == 0:
            # Both 0/0 and a nonzero constant difference have no estimable noise.
            # Retain the effect but never silently turn this degeneracy into p=0.
            statistic, pvalue, status = None, None, "zero_difference_variance"
        else:
            statistic = diff / math.sqrt(variance / self.n)
            require(math.isfinite(statistic), "paired statistic overflow")
            pvalue = float(2 * student_t.sf(abs(statistic), self.n - 1))
            status = "ok"
        pooled_mean = (self.mean[0] + self.mean[1]) / 2
        pooled_var = (self.m2[0] + self.m2[1] + self.n * ((self.mean[0]-pooled_mean)**2 +
                      (self.mean[1]-pooled_mean)**2)) / (2*self.n)
        require(math.isfinite(float(pooled_var)), "pooled variance overflow")
        effect = diff / math.sqrt(pooled_var) if pooled_var > 0 else None
        require(effect is None or math.isfinite(effect), "effect overflow")
        return {"n_words": int(self.n), "df": int(self.n-1), "pre_mean": float(self.mean[0]),
                "post_mean": float(self.mean[1]), "pre_minus_post": diff,
                "source_pooled_sd_effect": effect, "paired_t": statistic,
                "p_two_sided": pvalue, "status": status}


def evaluate(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    require(manifest.get("schema_version") == 1, "schema_version must be 1")
    require(manifest.get("task_id") == TASK_ID, "wrong task_id")
    require(manifest.get("sample_rate_hz") == SAMPLE_RATE, "source sample rate must be 2048 Hz")
    scope = manifest.get("scope")
    require(scope in ("engineering_control", "declared_source_population"), "invalid scope")
    for name in ("timing_sha256", "electrode_inventory_sha256", "processing_sha256"):
        fingerprint(manifest.get(name), name)
    require(isinstance(manifest.get("processing_description"), str) and manifest["processing_description"].strip(), "processing_description required")
    require(manifest.get("selection_policy") == "all_declared_electrodes_and_words", "data-dependent selection is not supported")
    subjects = manifest.get("subjects")
    require(isinstance(subjects, list) and bool(subjects), "subjects required")
    seen_subjects, expected = set(), {}
    exclusions = []
    for subject in subjects:
        sid = subject.get("subject_id")
        require(sid in SOURCE_RUNS and sid not in seen_subjects, "unknown or duplicate source subject")
        seen_subjects.add(sid)
        electrodes = string_ids(subject.get("electrode_ids"), "electrode_ids")
        runs = string_ids(subject.get("run_ids"), "run_ids")
        require(set(runs) <= set(SOURCE_RUNS[sid]), "unknown source run")
        excluded = subject.get("excluded_electrodes", [])
        require(isinstance(excluded, list), "excluded_electrodes must be a list")
        excluded_ids = []
        for item in excluded:
            require(isinstance(item, dict) and isinstance(item.get("electrode_id"), str) and item["electrode_id"].strip(), "excluded electrode id required")
            require(isinstance(item.get("reason"), str) and item["reason"].strip(), "exclusion reason required")
            fingerprint(item.get("evidence_sha256"), "exclusion evidence")
            excluded_ids.append(item["electrode_id"])
            exclusions.append({"subject_id": sid, **item})
        require(len(excluded_ids) == len(set(excluded_ids)) and not set(excluded_ids) & set(electrodes), "excluded electrodes overlap or repeat")
        for rid in runs:
            expected[(sid, rid)] = electrodes
    if scope == "declared_source_population":
        require(seen_subjects == set(SOURCE_RUNS), "source population requires all ten subjects")
        require(set(expected) == {(s, r) for s, rr in SOURCE_RUNS.items() for r in rr}, "source population requires all 26 runs")
    recordings = manifest.get("recordings")
    require(isinstance(recordings, list) and len(recordings) == len(expected), "recording inventory count mismatch")
    moments: dict[tuple[str, str, int], PairedMoments] = {}
    run_results, receipts, seen_runs = [], [], set()
    root = root.resolve()
    for recording in recordings:
        key = recording.get("subject_id"), recording.get("run_id")
        require(key in expected and key not in seen_runs, "unexpected or repeated recording")
        seen_runs.add(key)
        rel = recording.get("path")
        require(isinstance(rel, str) and rel and not Path(rel).is_absolute(), "recording path must be relative")
        path = (root / rel).resolve()
        require(path.is_relative_to(root), "recording escapes input root")
        expected_hash = fingerprint(recording.get("sha256"), "recording sha256")
        require(sha256(path) == expected_hash, "recording checksum mismatch")
        with np.load(path, allow_pickle=False) as arrays:
            require(set(arrays.files) == {"epochs", "word_ids", "electrode_ids", "onset_samples"}, "NPZ must contain epochs, word_ids, electrode_ids, onset_samples only")
            electrode_ids = arrays["electrode_ids"].tolist()
            word_ids = arrays["word_ids"].tolist()
            string_ids(electrode_ids, "array electrode_ids")
            string_ids(word_ids, "array word_ids")
            require(electrode_ids == expected[key], "electrode identity or order differs from inventory")
            require(len(word_ids) == recording.get("n_words") and len(word_ids) >= 2, "word count mismatch or fewer than two words")
            # A separate ordered identity digest prevents accepting the right word count
            # with missing/replaced/reordered words. It is still caller-supplied evidence.
            identity_bytes = json.dumps(word_ids, ensure_ascii=False, separators=(",", ":")).encode()
            require(hashlib.sha256(identity_bytes).hexdigest() == fingerprint(recording.get("word_ids_sha256"), "word_ids_sha256"), "word identity digest mismatch")
            onsets = arrays["onset_samples"]
            require(onsets.shape == (len(word_ids),) and np.issubdtype(onsets.dtype, np.integer), "onset_samples must be a word-length integer vector")
            require((onsets >= 0).all() and (onsets[1:] >= onsets[:-1]).all(), "onsets must be nonnegative chronological samples")
            epochs = arrays["epochs"]
            require(epochs.shape[:2] == (len(electrode_ids), len(word_ids)), "epoch axes disagree with identities")
            pre, post = window_means(epochs, manifest.get("epoch_first_sample"))
        for ei, electrode in enumerate(electrode_ids):
            for wi in range(len(WINDOWS)):
                m = moments.setdefault((key[0], electrode, wi), PairedMoments())
                m.add(pre[ei, :, wi], post[ei, :, wi])
                local = PairedMoments()
                local.add(pre[ei, :, wi], post[ei, :, wi])
                run_results.append({"subject_id": key[0], "run_id": key[1], "electrode_id": electrode,
                                    "window_index": wi, **local.result()})
        receipts.append({"subject_id": key[0], "run_id": key[1], "path": rel,
                         "sha256": expected_hash, "bytes": path.stat().st_size, "n_words": len(word_ids),
                         "word_ids_sha256": recording["word_ids_sha256"]})
    require(seen_runs == set(expected), "missing expected recording")
    family_size = len(moments)
    results = []
    for (sid, electrode, wi), moment in sorted(moments.items()):
        result = moment.result()
        pvalue = result["p_two_sided"]
        adjusted = min(1.0, pvalue * family_size) if pvalue is not None else None
        results.append({"subject_id": sid, "electrode_id": electrode, "window_index": wi,
                        "sample_offsets": list(WINDOWS[wi]), **result,
                        "p_global_bonferroni": adjusted,
                        "passes_prospective_threshold": adjusted is not None and adjusted < 0.05})
    summaries = []
    for sid, electrode in sorted({(r["subject_id"], r["electrode_id"]) for r in results}):
        rows = [r for r in results if r["subject_id"] == sid and r["electrode_id"] == electrode]
        valid = [r for r in rows if r["p_two_sided"] is not None]
        best = min(valid, key=lambda r: (r["p_two_sided"], r["window_index"])) if valid else None
        summaries.append({"subject_id": sid, "electrode_id": electrode,
                          "minimum_p_window": best["window_index"] if best else None,
                          "minimum_p_two_sided": best["p_two_sided"] if best else None,
                          "effect_at_minimum_p": best["source_pooled_sd_effect"] if best else None,
                          "any_window_passes": any(r["passes_prospective_threshold"] for r in rows)})
    return {"schema_version": 1, "task_id": TASK_ID, "source_revision": SOURCE_REVISION,
            "endpoint": "fixed_five_pair_word_responsiveness", "scope": scope,
            "inference_status": "descriptive_source_kernel_with_prospective_correction",
            "multiplicity": {"method": "global_bonferroni", "family_size": family_size, "alpha": 0.05,
                             "family": "all declared retained subject-electrodes times five windows, including degenerate tests"},
            "results": results, "electrodes": summaries, "per_run_descriptive_results": run_results,
            "input_receipts": receipts, "excluded_electrodes": exclusions,
            "n_subjects": len(seen_subjects), "n_runs": len(seen_runs),
            "source_run_inventory_declared_complete": seen_runs == {(s, r) for s, rr in SOURCE_RUNS.items() for r in rr},
            "authentic_population_verified": False,
            "admission": {"research_qualified": False, "full_contract_complete": False,
                          "native_reference_verified": False, "binary_reward_registered": False},
            "holds": HOLDS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_bytes = args.manifest.read_bytes()
    result = evaluate(json.loads(manifest_bytes), args.input_root)
    result["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
