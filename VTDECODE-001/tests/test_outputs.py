"""Grading checks for VTDECODE-001 (reproduce the Haxby VT decoding accuracy).

Ground truth (validated before release; nilearn 0.13.1 / scikit-learn 1.8.0, Haxby
subject 1, mask_vt, drop rest, NiftiMasker zscore_sample+detrend, SVC linear C=1):

  leave-one-run-out (CORRECT, run-blocked) : cv_accuracy = 0.722
  random 8-fold      (LEAKY)               : cv_accuracy = 0.958   (chance = 0.125)

Each object category is presented as a sustained block within a run, so volumes from
the same run are strongly temporally autocorrelated. A random k-fold split lets
near-adjacent volumes from one block appear in both train and test -> the accuracy is
inflated to ~0.96. Blocking the cross-validation by acquisition run (leave-one-run-out)
removes that leakage and gives the honest ~0.72.

The task pins the masker and classifier and asks only for "the cross-validated decoding
accuracy" -- it never names the fold scheme. A submission that reports the leaky
random-fold ~0.96 fails; the run-blocked ~0.72 passes.
"""
import json
import math
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.722   # correct, leave-one-run-out
TOL = 0.06         # admits legitimate run-blocked variants; excludes the leaky ~0.96 (0.236 away)
CHANCE = 0.125

# keys that look like a reported accuracy / decoding score ...
_ACC_KEY = re.compile(r"acc|score", re.I)
# ... but NOT a per-fold value, a chance level, a spread, a train score, or an explicitly
# leaky / naive / random comparison the submission may also have recorded.
_EXCL_KEY = re.compile(
    r"chance|std|sem|var|err|train|fold|per[_-]?|class|categ|base|null|shuffl|permut|"
    r"rand|kfold|k_fold|leak|naive|\bci\b|lower|upper|\bmin\b|\bmax\b|conf", re.I)


def _iter_scalars(obj, key=""):
    """Yield (nearest-dict-key, scalar) over a nested JSON object; list items inherit
    their parent key so per-fold arrays stay tagged with their (excluded) key name."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _iter_scalars(v, str(k))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_scalars(v, key)
    else:
        yield key, obj


def _accuracy_candidates():
    """Every plausible *headline* accuracy the submission reports, at any depth, in any
    JSON file, plus accuracies stated in prose. Percentages are normalised to 0-1."""
    cands = []
    for p in sorted(OUT.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for key, val in _iter_scalars(obj):
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                continue
            if not math.isfinite(val):
                continue
            if not _ACC_KEY.search(key) or _EXCL_KEY.search(key):
                continue
            if 0.0 <= val <= 1.0:
                cands.append(float(val))
            elif 1.0 < val <= 100.0:
                cands.append(float(val) / 100.0)
    # prose fallback: numbers stated next to the word "accuracy" or as a percentage
    prose = ""
    for name in ("findings.md", "run_metadata.json", "decoding_results.json"):
        fp = OUT / name
        if fp.exists():
            prose += "\n" + fp.read_text(encoding="utf-8")
    for m in re.finditer(r"accuracy[^0-9%\n]{0,40}?(\d{1,3}(?:\.\d+)?)\s*%", prose, re.I):
        cands.append(float(m.group(1)) / 100.0)
    for m in re.finditer(r"accuracy[^0-9\n]{0,40}?(0?\.\d+)", prose, re.I):
        cands.append(float(m.group(1)))
    for m in re.finditer(r"(\d{1,3}(?:\.\d+)?)\s*%[^.\n]{0,25}accuracy", prose, re.I):
        cands.append(float(m.group(1)) / 100.0)
    for m in re.finditer(r"(0?\.\d+)[^0-9\n]{0,25}accuracy", prose, re.I):
        cands.append(float(m.group(1)))
    return [c for c in cands if 0.0 <= c <= 1.0]


def test_accuracy_reported():
    # A parseable, above-chance decoding accuracy was produced at all.
    cands = _accuracy_candidates()
    assert cands, "no cross-validated decoding accuracy could be parsed from the submission"
    assert max(cands) > CHANCE + 0.05, (
        f"reported accuracies {sorted(set(round(c,3) for c in cands))} are at/below chance "
        f"({CHANCE}) -- the decoder was not evaluated properly")


def test_cross_validated_accuracy_matches_run_blocked():
    # The honest, leakage-free cross-validated accuracy is ~0.722 (leave-one-run-out).
    # A random-fold pipeline reports ~0.958; that must NOT pass. So we require the
    # submission to have reported an accuracy consistent with the run-blocked estimate.
    cands = _accuracy_candidates()
    best = min(cands, key=lambda c: abs(c - EXPECTED)) if cands else None
    assert best is not None and abs(best - EXPECTED) < TOL, (
        f"reported cross-validated accuracy is not consistent with the run-blocked estimate "
        f"{EXPECTED:.3f} +/- {TOL} (chance {CHANCE}). Parsed accuracies: "
        f"{sorted(set(round(c,3) for c in cands))}. A value near 0.96 is the temporally-leaky "
        f"random-fold artifact, not the honest out-of-sample decoding accuracy.")
