"""Grading checks for MIYAWAKI-001 (reproduce the Miyawaki visual-pattern decoding accuracy).

Ground truth (validated before release; nilearn 0.13.1 / scikit-learn 1.8.0, 20 random-image
runs, dataset.mask, per-run zscore_sample + detrend, label shifted +2 volumes, drop rest,
Ridge(alpha=1.0) thresholded at 0.5):

  leave-one-run-out (CORRECT, block-blocked) : mean_pixel_accuracy = 0.593
  random 10-fold      (LEAKY)                : mean_pixel_accuracy = 0.639   (chance ~ 0.50)

Each random contrast pattern is held on screen for several seconds, so a block of consecutive
BOLD volumes shares the SAME 100-pixel label and neighbouring volumes are strongly temporally
autocorrelated. A random k-fold split over volumes lets near-duplicate volumes from one block
(identical target, correlated activity) appear in both train and test -> the accuracy is
inflated to ~0.64. Blocking the cross-validation by acquisition run (leave-one-run-out) removes
that leakage and gives the honest ~0.59. Every leakage-free scheme (leave-one-run-out,
group-k-fold by run, group-k-fold by stimulus block) lands at 0.589-0.598; every random-volume
scheme lands at 0.632-0.654.

The task pins the masker, alignment, decoder and metric and asks only for "the cross-validated
mean pixel decoding accuracy" -- it never names the fold scheme. A submission that reports the
leaky random-fold ~0.64 fails; the run-blocked ~0.59 passes.
"""
import json
import math
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.593   # correct, leave-one-run-out
TOL = 0.025        # admits legitimate leakage-free variants; excludes the leaky >=0.632
CHANCE = 0.50

# keys that look like a reported accuracy / decoding score ...
_ACC_KEY = re.compile(r"acc|score", re.I)
# ... but NOT a per-fold value, a chance level, a spread, a train score, or an explicitly
# leaky / naive / random comparison the submission may also have recorded.
_EXCL_KEY = re.compile(
    r"chance|std|sem|var|err|train|fold|base|null|shuffl|permut|"
    r"rand|kfold|k_fold|leak|naive|circul|\bci\b|lower|upper|\bmin\b|\bmax\b|conf", re.I)


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
    # A parseable, above-chance mean pixel decoding accuracy was produced at all.
    cands = _accuracy_candidates()
    assert cands, "no cross-validated mean pixel decoding accuracy could be parsed from the submission"
    assert max(cands) > CHANCE + 0.05, (
        f"reported accuracies {sorted(set(round(c,3) for c in cands))} are at/near chance "
        f"({CHANCE}) -- the decoder was not evaluated properly")


def test_cross_validated_accuracy_matches_run_blocked():
    # The honest, leakage-free cross-validated mean pixel accuracy is ~0.593 (leave-one-run-out).
    # A random-fold pipeline reports ~0.639; that must NOT pass. So we require the submission to
    # have reported an accuracy consistent with the run-blocked estimate.
    cands = _accuracy_candidates()
    best = min(cands, key=lambda c: abs(c - EXPECTED)) if cands else None
    assert best is not None and abs(best - EXPECTED) < TOL, (
        f"reported cross-validated mean pixel accuracy is not consistent with the run-blocked "
        f"estimate {EXPECTED:.3f} +/- {TOL} (chance {CHANCE}). Parsed accuracies: "
        f"{sorted(set(round(c,3) for c in cands))}. A value near 0.64 is the temporally-leaky "
        f"random-fold artifact, not the honest out-of-sample decoding accuracy.")
