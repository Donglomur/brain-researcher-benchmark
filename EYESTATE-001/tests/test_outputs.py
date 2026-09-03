"""Grading checks for EYESTATE-001 (reproduce the ABIDE eyes-open vs eyes-closed
cross-validated decoding accuracy).

Ground truth (validated before release; nilearn 0.13.1 / scikit-learn 1.8.0, ABIDE cpac
filt_noglobal rois_cc200, N=1035, Pearson-correlation connectivity, LinearSVC C=1, balanced
accuracy):

  leave-one-site-out (CORRECT, site-blocked) : balanced_accuracy = 0.737
  random 10-fold     (LEAKY)                 : balanced_accuracy = 0.867   (chance = 0.5)

In ABIDE each acquisition SITE used one eyes-open/closed protocol, so eye status is almost
perfectly aligned with the scanning site, and connectivity carries a strong site-specific
fingerprint. A random k-fold split puts subjects from a site in both train and test, so the
classifier reads eye status off the site fingerprint and the accuracy is inflated to ~0.87.
Blocking the cross-validation by acquisition site (leave-one-site-out, or any site-grouped
scheme) forces generalisation to unseen sites, leaving only the genuine, transferable
eyes-open/closed effect (~0.74).

The task pins the subject set, atlas, connectivity, classifier and metric and asks only for
"the cross-validated balanced accuracy" -- it never names the fold scheme or the site
confound. A submission that reports the leaky random-fold ~0.87 fails; a site-blocked
~0.74 (leave-one-site-out ~0.737, or a stratified site-grouped scheme ~0.75-0.77) passes.
"""
import json
import math
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.737   # correct, leave-one-site-out
TOL = 0.09         # admits site-blocked variants (~0.737-0.774); excludes the leaky ~0.867
CHANCE = 0.5

# keys that look like a reported balanced accuracy / decoding score ...
_ACC_KEY = re.compile(r"bacc|balanced|acc|score", re.I)
# ... but NOT a per-fold value, a chance level, a spread, a train score, or an explicitly
# leaky / naive / random / unblocked comparison the submission may also have recorded.
_EXCL_KEY = re.compile(
    r"chance|std|sem|var|err|train|fold|per[_-]?|base|null|shuffl|permut|"
    r"rand|kfold|k_fold|leak|naive|unblock|mixed|within[_-]?site|\bci\b|lower|upper|"
    r"\bmin\b|\bmax\b|conf", re.I)


def _iter_scalars(obj, key=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _iter_scalars(v, str(k))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_scalars(v, key)
    else:
        yield key, obj


def _accuracy_candidates():
    """Every plausible *headline* balanced accuracy the submission reports, at any depth, in
    any JSON file, plus accuracies stated in prose. Percentages are normalised to 0-1."""
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
    prose = ""
    for name in ("findings.md", "run_metadata.json", "eye_decoding_results.json"):
        fp = OUT / name
        if fp.exists():
            prose += "\n" + fp.read_text(encoding="utf-8")
    for m in re.finditer(r"(?:balanced\s+)?accuracy[^0-9%\n]{0,40}?(\d{1,3}(?:\.\d+)?)\s*%", prose, re.I):
        cands.append(float(m.group(1)) / 100.0)
    for m in re.finditer(r"(?:balanced\s+)?accuracy[^0-9\n]{0,40}?(0?\.\d+)", prose, re.I):
        cands.append(float(m.group(1)))
    for m in re.finditer(r"(\d{1,3}(?:\.\d+)?)\s*%[^.\n]{0,25}accuracy", prose, re.I):
        cands.append(float(m.group(1)) / 100.0)
    for m in re.finditer(r"(0?\.\d+)[^0-9\n]{0,25}accuracy", prose, re.I):
        cands.append(float(m.group(1)))
    return [c for c in cands if 0.0 <= c <= 1.0]


def test_accuracy_reported():
    # A parseable, above-chance decoding accuracy was produced at all.
    cands = _accuracy_candidates()
    assert cands, "no cross-validated balanced accuracy could be parsed from the submission"
    assert max(cands) > CHANCE + 0.05, (
        f"reported accuracies {sorted(set(round(c,3) for c in cands))} are at/below chance "
        f"({CHANCE}) -- the decoder was not evaluated properly")


def test_cross_validated_accuracy_is_site_blocked():
    # The honest, leakage-free cross-validated balanced accuracy is ~0.737 (leave-one-site-out).
    # A random-fold pipeline reports ~0.867; that must NOT pass. So we require the submission
    # to have reported an accuracy consistent with the site-blocked estimate.
    cands = _accuracy_candidates()
    best = min(cands, key=lambda c: abs(c - EXPECTED)) if cands else None
    assert best is not None and abs(best - EXPECTED) < TOL, (
        f"reported cross-validated balanced accuracy is not consistent with the site-blocked "
        f"estimate {EXPECTED:.3f} +/- {TOL} (chance {CHANCE}). Parsed accuracies: "
        f"{sorted(set(round(c,3) for c in cands))}. A value near 0.87 is the site-fingerprint-leaky "
        f"random-fold artifact, not the honest cross-site decoding accuracy.")
