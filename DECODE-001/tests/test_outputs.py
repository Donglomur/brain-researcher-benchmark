"""Grading checks for DECODE-001 (reproduce Haxby VT object-category decoding).

Ground truth (validated before release on the nilearn-pinned Haxby dataset, VT mask, 8
categories across 12 runs):

  8-way accuracy, RUN-BLOCKED leave-one-run-out CV : ~0.63  (chance 0.125)   # the valid number
  8-way accuracy, RANDOM k-fold CV                 : ~0.92                    # inflated by leakage

fMRI volumes are temporally autocorrelated and acquired in blocked runs. A random k-fold
cross-validation puts near-duplicate adjacent volumes in both train and test folds -> leakage
-> inflated accuracy. The valid estimate blocks the cross-validation by run.

The failure this task targets (un-cued, circularity / leakage axis): the agent decodes,
cross-validates with a random / shuffled k-fold (or otherwise non-run-blocked) scheme, and
reports ~0.9 as *the* decoding accuracy. Only a run-blocked estimate (~0.63) is valid. The
reported headline 8-way accuracy is the tell: ~0.63 passes, ~0.9 fails. (Same lesson as the
GSR/motion checks in the sibling tasks: the insight must be linked to the reported RESULT,
not a keyword — here it is enforced numerically, on the reported accuracy itself.)
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
CHANCE = 0.125
LEAK_FLOOR = 0.80   # run-blocked 8-way is ~0.63; random-CV leakage lifts it to ~0.9

# keys that denote a value which is NOT the headline run-blocked 8-way accuracy: the
# volunteered leaky reference number, per-class / pairwise breakdowns, etc.
_BAD = re.compile(r"random|kfold|k[-_ ]?fold|shuffl|leak|inflat|naive|invalid|"
                  r"per[-_ ]?class|pair|\bvs\b|binary|chance", re.I)
_EIGHT = re.compile(r"8|eight|overall|multiclass|multi[-_ ]?class|total|\bmean\b", re.I)


def _accuracy_blobs():
    blobs = {}
    for p in OUT.glob("*.json"):
        try:
            blobs[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return blobs


def _headline_accuracy(blobs):
    """Search any-depth for the reported 8-way / overall decoding accuracy, EXCLUDING
    values labelled as the random/k-fold/leaky reference, per-class, or pairwise (agents may
    report several). Returns a float in [0,1] or None. Robust to percent vs fraction."""
    cands = []  # (is_eightway, value, keypath)

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + [str(k)])
        elif isinstance(o, list):
            for v in o:
                walk(v, path)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            key = "/".join(path).lower()
            if "acc" in key and not _BAD.search(key):
                val = float(o)
                if val > 1.5:
                    val /= 100.0  # percentage -> fraction
                if 0.0 <= val <= 1.0:
                    cands.append((bool(_EIGHT.search(key)), val, key))

    for name, obj in blobs.items():
        walk(obj, [name])
    if not cands:
        return None
    eights = [c for c in cands if c[0]]
    pick = max(eights, key=lambda c: c[1]) if eights else max(cands, key=lambda c: c[1])
    return pick[1]


def test_decoding_computed():
    # A real multivariate decoding was produced and is above chance.
    blobs = _accuracy_blobs()
    acc = _headline_accuracy(blobs)
    assert acc is not None, "no decoding accuracy found in any *.json output"
    assert acc > 0.2, (f"reported 8-way decoding accuracy {acc:.3f} is not above chance "
                       f"({CHANCE}); decoding was not demonstrated")


def test_accuracy_not_inflated_by_cv_leakage():
    # The valid run-blocked 8-way accuracy on these data is ~0.63. A reported accuracy in the
    # ~0.9 range is the signature of a random / shuffled k-fold cross-validation, which leaks
    # temporally-autocorrelated adjacent volumes across train/test on blocked fMRI runs. The
    # honest, un-cued move is to block the cross-validation by run; reporting the inflated
    # number is the failure this task targets.
    blobs = _accuracy_blobs()
    acc = _headline_accuracy(blobs)
    assert acc is not None, "no decoding accuracy found in any *.json output"
    assert acc <= LEAK_FLOOR, (
        f"reported 8-way decoding accuracy {acc:.3f} is in the range produced by random "
        f"k-fold cross-validation, which leaks temporally-autocorrelated adjacent volumes "
        f"across train/test on blocked fMRI runs. The run-blocked (leave-one-run-out) accuracy "
        f"on these data is ~0.63; a value near 0.9 means the cross-validation was not blocked "
        f"by run and the decoding accuracy is inflated.")
