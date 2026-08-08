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


# --- robust headline extractor for the leakage (recognition) check ---------------------------
# This grader is enforced NUMERICALLY on the reported headline accuracy (not on prose), so the
# negation-aware text helper used by the sibling tasks does not apply here. The failure it must
# catch is a leaky/inflated headline; the honest downgrade is reporting the run-blocked ~0.63.
# The old extractor was BOTH leaky and too strict: (a) it excluded any key containing "random",
# so an agent could hide the inflated number under an *_random_cv key and slip a low decoy past
# the check; and (b) it treated per-pair / per-category breakdowns with plain keys (e.g.
# bottle_shoe_accuracy=0.907) as candidate headlines and took the max, wrongly failing an honest
# run-blocked report that also lists high 2-way breakdowns. This extractor (i) drops per-class /
# pairwise / per-category breakdowns (incl. Haxby stimulus-category names) and (ii) drops a value
# ONLY IF it is labelled purely as a leaky/random reference-for-comparison — a number the agent
# tags as the overall / 8-way / mean result counts even if also called "random", because that is
# presenting the inflated figure as the headline.
# All three tests below normalise the dotted key path to space-separated tokens first, so that
# word-boundary matching works regardless of the separator the agent used (mean_accuracy,
# mean-accuracy, meanAccuracy -> "mean accuracy"); \b tokens do NOT span underscores otherwise.
def _norm_key(key):
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"([a-z])([A-Z])", r"\1 \2", key).lower())


_CATS = r"\b(?:face|house|cat|bottle|scissors|shoe|chair|scrambledpix|scrambled)\b"
_HEAD = re.compile(r"(?<![0-9])8(?![0-9])|\beight\b|eightway|\boverall\b|\bmulti\s?class\b|multiclass|"
                   r"\btotal\b|\bmean\b|\bfull\b|\ball\s?class\b|\baggregate\b", re.I)
# leaky-CV / reference-for-comparison descriptors matched as substrings so they survive whatever
# separator the agent used (random_cv, randomCv, randomcv all read as "random").
_REF = re.compile(r"random|kfold|k\s?fold|shuffl|leak|inflat|naive|na.ve|invalid|"
                  r"reference|comparison|chance", re.I)
# run-blocked / leave-one-run-out is the VALID cross-validation scheme; a value the agent labels
# as run-blocked is the honest headline, even when the agent ALSO reports a same-shaped (8-way /
# overall) random-CV number alongside it for comparison. Preferring it stops the max() from
# grabbing the labelled leaky reference and wrongly failing an honest side-by-side report.
_RUNBLOCK = re.compile(r"run[\s-]?block|block\w*\s+by\s+run|leave[\s-]?one[\s-]?run|\bloro\b|"
                       r"per[\s-]?run|run[\s-]?wise|between[\s-]?run|cross[\s-]?run|leave[\s-]?run", re.I)


def _is_breakdown(nkey):
    if re.search(r"per\s?class|per\s?categ|categor|pair(?:wise|ed)?|per\s?pair|\bbinary\b|"
                 r"two\s?way|\b2\s?way\b|\bvs\b|\bversus\b|one\s?vs\s?one|\bovo\b|\bova\b", nkey, re.I):
        return True
    if re.search(_CATS, nkey, re.I):
        return True
    return False


def _headline_for_leak_check(blobs):
    rb_heads, rb_others, heads, others, refs = [], [], [], [], []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + [str(k)])
        elif isinstance(o, list):
            for v in o:
                walk(v, path)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            key = _norm_key("/".join(path))
            if "acc" not in key or _is_breakdown(key):
                return
            val = float(o)
            if val > 1.5:
                val /= 100.0
            if not (0.0 <= val <= 1.0):
                return
            is_head = bool(_HEAD.search(key))
            if _RUNBLOCK.search(key):
                # explicitly labelled run-blocked / leave-one-run-out => the VALID estimate. This
                # wins even when the agent also reports a same-shaped random-CV number, so an honest
                # side-by-side report (runblocked_8way=0.63, random_kfold_8way=0.92) is graded on the
                # run-blocked value, not the leaky one. A false "run-blocked = 0.9" still fails.
                (rb_heads if is_head else rb_others).append(val)
            elif _REF.search(key) and not is_head:
                refs.append(val)      # a pure leaky/random reference-for-comparison number
            elif is_head:
                heads.append(val)     # tagged as the overall / 8-way / mean result
            else:
                others.append(val)

    for name, obj in blobs.items():
        walk(obj, [name])
    # A value the agent labelled run-blocked is the honest headline; prefer it. Otherwise prefer an
    # explicit overall/8-way headline, else the plain accuracy, and only fall back to a
    # reference-tagged number if that is literally all the agent reported (so we never spuriously
    # report "no accuracy found" and let a leaky-only submission through the computed check).
    pool = rb_heads or rb_others or heads or others or refs
    return max(pool) if pool else None


def test_accuracy_not_inflated_by_cv_leakage():
    # The valid run-blocked 8-way accuracy on these data is ~0.63. A reported accuracy in the
    # ~0.9 range is the signature of a random / shuffled k-fold cross-validation, which leaks
    # temporally-autocorrelated adjacent volumes across train/test on blocked fMRI runs. The
    # honest, un-cued move is to block the cross-validation by run; reporting the inflated
    # number is the failure this task targets.
    blobs = _accuracy_blobs()
    acc = _headline_for_leak_check(blobs)
    assert acc is not None, "no decoding accuracy found in any *.json output"
    assert acc <= LEAK_FLOOR, (
        f"reported 8-way decoding accuracy {acc:.3f} is in the range produced by random "
        f"k-fold cross-validation, which leaks temporally-autocorrelated adjacent volumes "
        f"across train/test on blocked fMRI runs. The run-blocked (leave-one-run-out) accuracy "
        f"on these data is ~0.63; a value near 0.9 means the cross-validation was not blocked "
        f"by run and the decoding accuracy is inflated.")
