"""Grading checks for OBJCAT-001 (reproduce the Haxby whole-brain object-decoding accuracy).

Ground truth (validated before release; nilearn 0.13.1 / scikit-learn 1.8.0, subject 2,
whole-brain mask, drop rest, NiftiMasker per-run zscore_sample + detrend, 500 voxels by
highest ANOVA F, SVC linear C=1, leave-one-run-out):

  feature selection INSIDE each fold (CORRECT, nested) : cv_accuracy = 0.656
  feature selection on ALL data      (CIRCULAR)        : cv_accuracy = 0.757   (chance = 0.125)

Reducing to the 500 most category-selective voxels is a category-driven step. If those
voxels are chosen once on the WHOLE dataset (including the held-out run's volumes) and the
SVM is then cross-validated on them, the selection has already seen the test folds and the
accuracy is inflated to ~0.76 (circular analysis / double dipping). The correct estimate
re-runs the ANOVA voxel selection inside each cross-validation fold, on the training runs
only, giving the honest ~0.66. The choice is invariant to the SVM C over 0.5-5.0.

The task pins the subject, mask, sample selection, masker, number of selected voxels,
classifier and cross-validation scheme and asks only for "the cross-validated 8-way
decoding accuracy" -- it never says where the selection must happen. A submission that
reports the circular ~0.76 fails; the nested ~0.66 passes.
"""
import json
import math
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.656   # correct, feature selection nested within each fold
TOL = 0.045        # admits legitimate nested variants; excludes the circular ~0.757
CHANCE = 0.125

# keys that look like a reported accuracy / decoding score ...
_ACC_KEY = re.compile(r"acc|score", re.I)
# ... but NOT a per-fold value, a chance level, a spread, a train score, or an explicitly
# circular / select-once / naive comparison the submission may also have recorded.
_EXCL_KEY = re.compile(
    r"chance|std|sem|var|err|train|fold|per[_-]?|base|null|shuffl|permut|"
    r"rand|kfold|k_fold|leak|naive|circul|select_once|selectonce|\bci\b|"
    r"lower|upper|\bmin\b|\bmax\b|conf", re.I)


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
    # A parseable, well-above-chance 8-way decoding accuracy was produced at all.
    cands = _accuracy_candidates()
    assert cands, "no cross-validated decoding accuracy could be parsed from the submission"
    assert max(cands) > CHANCE + 0.05, (
        f"reported accuracies {sorted(set(round(c,3) for c in cands))} are at/near chance "
        f"({CHANCE}) -- the decoder was not evaluated properly")


def test_cross_validated_accuracy_is_not_circular():
    # The honest, non-circular cross-validated accuracy is ~0.656 (selection nested in CV).
    # A select-once pipeline reports ~0.757; that must NOT pass. So we require the submission
    # to have reported an accuracy consistent with the nested estimate.
    cands = _accuracy_candidates()
    best = min(cands, key=lambda c: abs(c - EXPECTED)) if cands else None
    assert best is not None and abs(best - EXPECTED) < TOL, (
        f"reported cross-validated accuracy is not consistent with the non-circular estimate "
        f"{EXPECTED:.3f} +/- {TOL} (chance {CHANCE}). Parsed accuracies: "
        f"{sorted(set(round(c,3) for c in cands))}. A value near 0.76 is the circular "
        f"select-once artifact (feature selection that saw the held-out folds), not the honest "
        f"out-of-sample decoding accuracy.")
