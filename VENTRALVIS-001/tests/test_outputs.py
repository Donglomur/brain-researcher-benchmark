"""Grading checks for VENTRALVIS-001 (reproduce Haxby VT object-category decoding).

Ground truth (validated; receipt in the private calibration.md) on the nilearn-pinned Haxby
dataset, VT mask (464 voxels), 8 categories across 12 runs:

  8-way accuracy, RUN-BLOCKED leave-one-run-out CV : ~0.63  (chance 0.125)   # the valid number
  8-way accuracy, RANDOM (shuffled) 5-fold CV      : ~0.92                    # inflated by leakage

fMRI volumes are temporally autocorrelated and acquired in blocked runs. A random k-fold split
puts near-duplicate adjacent volumes from the SAME run in both train and test folds -> temporal
leakage -> inflated accuracy. The valid estimate blocks the cross-validation BY RUN (groups =
Haxby `chunks`), so no run ever appears in both train and test.

The failure this task targets (un-cued, circularity / leakage axis): the agent decodes,
cross-validates with a random / shuffled k-fold (or otherwise non-run-blocked) scheme, and reports
~0.9 as *the* decoding accuracy. Only a run-blocked estimate (~0.63) is valid.

These checks validate the actual DATA — a real above-chance accuracy, the real Haxby category
labels, sane sample/run counts, and (where reported) that the random-CV reference is genuinely
HIGHER than the run-blocked one and that the emitted CV folds are genuinely run-blocked (no run
crosses train/test) — not just the presence of a number or matching prose. An empty, naive
(inflated headline), or fabricated (fake labels / implausible values / backwards hidden-check)
submission fails; the honest run-blocked oracle passes.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
CHANCE = 0.125
LEAK_FLOOR = 0.80   # run-blocked 8-way is ~0.63; random-CV leakage lifts it to ~0.92
REAL_CATS = {"face", "house", "cat", "bottle", "scissors", "shoe", "chair", "scrambledpix"}


def _blobs():
    b = {}
    for p in OUT.glob("*.json"):
        try:
            b[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return b


def _findings():
    p = OUT / "findings.md"
    return p.read_text(encoding="utf-8").lower() if p.exists() else ""


def _norm_key(key):
    """Dotted/camel/underscore key path -> space-separated tokens, so \\b word matching and
    substring checks work regardless of the separator the agent used (mean_accuracy,
    mean-accuracy, meanAccuracy -> 'mean accuracy')."""
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"([a-z])([A-Z])", r"\1 \2", key).lower())


# --- key classifiers for accuracy extraction ------------------------------------------------
_CATS_RE = r"\b(?:face|house|cat|bottle|scissors|shoe|chair|scrambledpix|scrambled)\b"
_HEAD = re.compile(r"(?<![0-9])8(?![0-9])|\beight\b|eightway|\boverall\b|\bmulti\s?class\b|multiclass|"
                   r"\btotal\b|\bmean\b|\bfull\b|\ball\s?class\b|\baggregate\b", re.I)
# leaky-CV / reference-for-comparison descriptors (substring match so random_cv / randomCv read as
# "random"); "inflat"/"naive" included so a value the agent tags as the inflated reference is shelved.
_REF = re.compile(r"random|kfold|k\s?fold|shuffl|leak|inflat|naive|na.ve|invalid|reference|comparison",
                  re.I)
_LEAKY = re.compile(r"random|k\s?fold|shuffl|leak|inflat", re.I)   # a genuinely leaky ACCURACY number
_RUNBLOCK = re.compile(r"run[\s-]?block|block\w*\s+by\s+run|leave[\s-]?one[\s-]?run|\bloro\b|"
                       r"per[\s-]?run|run[\s-]?wise|between[\s-]?run|cross[\s-]?run|leave[\s-]?run|"
                       r"group\w*\s+by\s+run|by[\s-]?run", re.I)


def _is_breakdown(nkey):
    """True for per-class / pairwise / per-fold / stimulus-category numbers — never the headline."""
    if re.search(r"per\s?class|per\s?categ|categor|pair(?:wise|ed)?|per\s?pair|\bbinary\b|two\s?way|"
                 r"\b2\s?way\b|\bvs\b|\bversus\b|one\s?vs\s?one|\bovo\b|\bova\b|\bfold\b|per\s?fold",
                 nkey, re.I):
        return True
    if re.search(_CATS_RE, nkey, re.I):
        return True
    return False


def _collect_acc(blobs):
    """Walk every *.json; yield (normkey, value_as_fraction, is_head, is_runblock, is_leaky) for
    each numeric value on an 'acc'-keyed, non-breakdown path. Percent values are normalised."""
    out = []

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
            if 0.0 <= val <= 1.0:
                out.append((key, val, bool(_HEAD.search(key)),
                            bool(_RUNBLOCK.search(key)), bool(_LEAKY.search(key))))

    for name, obj in blobs.items():
        walk(obj, [name])
    return out


def _headline_accuracy(blobs):
    """The reported 8-way / overall decoding accuracy, EXCLUDING values labelled as the
    random/k-fold/leaky reference, per-class, pairwise, or per-fold. Prefers a run-blocked-labelled
    value, then an explicit 8-way/overall headline, then plain accuracy, and only falls back to a
    reference-tagged number if that is literally all the agent reported."""
    acc = _collect_acc(blobs)
    if not acc:
        return None
    rb_head = [v for k, v, h, rb, lk in acc if rb and h]
    rb_any = [v for k, v, h, rb, lk in acc if rb]
    ref = [v for k, v, h, rb, lk in acc if lk and not h and not rb]
    head = [v for k, v, h, rb, lk in acc if h and not rb and not (lk and not h)]
    other = [v for k, v, h, rb, lk in acc if not h and not rb and not lk]
    for pool in (rb_head, rb_any, head, other, ref):
        if pool:
            return max(pool)
    return None


# --- reported class labels and their reality ------------------------------------------------
def _reported_labels(blobs):
    """Labels the agent presents as the decoded classes: keys of a per-class-accuracy mapping, and
    items of a categories/classes/labels list."""
    labels = []

    def walk(o, key=""):
        if isinstance(o, dict):
            parent = _norm_key(key)
            if re.search(r"per\s?class|per\s?categ|class\s?acc|by\s?class|category\s?acc", parent):
                labels.extend([str(k) for k in o.keys() if isinstance(k, str)])
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            if re.search(r"categor|classes|\blabels?\b|\bclass\b", _norm_key(key)):
                labels.extend([str(x) for x in o if isinstance(x, str)])

    for obj in blobs.values():
        walk(obj)
    return labels


def test_decoding_computed():
    """Validate the ACTUAL data: a real above-chance 8-way accuracy, the real Haxby category
    labels, sane sample/run counts, accuracy values in range, and — where both are reported — the
    random-CV reference genuinely HIGHER than the run-blocked estimate (right direction).
    Empty / fabricated (fake labels, implausible values, backwards hidden-check) fails."""
    blobs = _blobs()
    assert blobs, "no *.json output found (empty submission)"

    acc = _headline_accuracy(blobs)
    assert acc is not None, "no decoding accuracy found in any *.json output"
    assert acc > 0.2, (f"reported 8-way decoding accuracy {acc:.3f} is not above chance "
                       f"({CHANCE}); decoding was not demonstrated")

    # reported class labels must be the real Haxby object categories (fabricated fake labels fail).
    labels = [l.strip().lower() for l in _reported_labels(blobs)]
    labels = [l for l in labels if l and l not in ("rest", "background")]
    if labels:
        real = [l for l in labels if l in REAL_CATS]
        assert len(real) >= 3, (
            f"fewer than 3 real Haxby category labels among reported classes {labels[:10]} "
            f"(expected from {sorted(REAL_CATS)}) — fabricated or wrong-dataset labels")
        assert len(real) >= 0.6 * len(labels), (
            f"most reported class labels {labels[:10]} are not real Haxby categories (fabricated?)")

    # every reported accuracy value (headline, per-class, per-fold, reference) must be a valid
    # fraction in [0,1] after percent-normalisation; an implausible value (e.g. 1.3) is fabricated.
    allacc = _collect_acc(blobs)
    assert allacc, "no accuracy values found in any *.json output"
    assert all(0.0 <= v <= 1.0 for _, v, _, _, _ in allacc), (
        "reported accuracy values are outside [0,1] after percent-normalisation (fabricated?)")

    # sample / run counts sane where reported (single-subject Haxby: ~864 non-rest volumes, 12 runs)
    def nums(pat):
        out = []
        def walk(o, key=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, str(k))
            elif isinstance(o, list):
                for v in o:
                    walk(v, key)
            elif isinstance(o, (int, float)) and not isinstance(o, bool):
                if re.search(pat, _norm_key(key), re.I):
                    out.append(float(o))
        for obj in blobs.values():
            walk(obj)
        return out

    ns = nums(r"n\s?samp|n\s?sample|\bsamples?\b|n\s?vol|n\s?trs?\b")
    if ns:
        assert any(100 <= int(v) <= 5000 for v in ns), f"implausible n_samples {ns} (Haxby ~864)"
    nr = nums(r"n\s?runs?\b|n\s?folds?\b|n\s?chunks?\b")
    if nr:
        assert any(4 <= int(v) <= 30 for v in nr), f"implausible n_runs/folds {nr} (Haxby = 12)"

    # hidden-check DIRECTION: if a random/leaky reference accuracy is reported alongside the
    # run-blocked headline, it must be at least as high (leakage inflates). A backwards claim
    # (random < run-blocked) is fabricated / physically wrong on these data.
    leaky = [v for k, v, h, rb, lk in allacc if lk and not rb]
    if leaky:
        assert max(leaky) >= acc - 0.02, (
            f"reported random/k-fold reference accuracy {max(leaky):.3f} is LOWER than the "
            f"run-blocked headline {acc:.3f}; random-CV leakage inflates accuracy, so this is the "
            f"wrong direction (fabricated hidden-check)")


# --- CV-fold structure: confirm no run crosses train/test -----------------------------------
def _cv_folds(blobs):
    """Find the reported list of leave-one-run-out folds (each a dict with a held-out test run and
    the training runs)."""
    found = []

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            if re.search(r"fold", _norm_key(key)) and o and isinstance(o[0], dict):
                if any(re.search(r"test.*run|run.*test|held", _norm_key(kk)) for d in o
                       if isinstance(d, dict) for kk in d.keys()):
                    found.append(o)
            for v in o:
                walk(v, key)

    for obj in blobs.values():
        walk(obj)
    return found[0] if found else []


def _fold_runs(fold):
    """(test_runs set, train_runs set) parsed from a fold dict, tolerant of scalar-or-list."""
    def as_ints(v):
        if isinstance(v, list):
            return {int(x) for x in v if isinstance(x, (int, float)) and not isinstance(x, bool)}
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return {int(v)}
        return set()

    test, train = set(), set()
    for k, v in fold.items():
        nk = _norm_key(k)
        if re.search(r"test.*run|run.*test|held.*out.*run|held.*run", nk):
            test |= as_ints(v)
        elif re.search(r"train.*run|run.*train|fit.*run", nk):
            train |= as_ints(v)
    return test, train


def _folds_run_blocked(folds):
    """True iff EVERY fold's held-out test run is a real single run absent from that fold's training
    runs (recomputed from the run ids themselves, not from any self-reported boolean)."""
    if not folds:
        return False
    seen_any = False
    for f in folds:
        if not isinstance(f, dict):
            return False
        test, train = _fold_runs(f)
        if not test or not train:
            return False
        seen_any = True
        if test & train:            # a run appears in both train and test -> leakage
            return False
    return seen_any


# --- negation-aware, downgrade-driven recognition helper (shared with sibling tasks) ---------
_NEG = (r"(?:not|no|n't|without|never|hardly|scarcely|far from|rather than|instead of|rule[sd]? out|"
        r"ruled out|free of|devoid of|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|"
        r"lacks?|lacking|absent|nothing|neither|fails? to|unlikely to)")


def _neg_before(text, start, window=48):
    pre = text[max(0, start - window):start]
    return re.search(r"(?<![a-z])" + _NEG + r"(?![a-z])[\s\w,'\"()-]{0,20}$", pre, re.I) is not None


def _unnegated(text, pat, window=48):
    for m in re.finditer(pat, text, re.I):
        if _neg_before(text, m.start(), window):
            continue
        if re.search(r"\b" + _NEG + r"\b", m.group(0), re.I):
            continue
        return True
    return False


def _recognises_cv_leakage(text):
    """findings.md recognises that a random/non-run-blocked CV inflates the accuracy (temporal
    leakage) and that blocking by run is the valid move. Negation-aware and downgrade-driven: a
    bare mention of 'cross-validation' or a dismissal ('run-blocking does not matter') does not
    pass."""
    concept = (r"random\s*k?-?\s*fold|k-?\s*fold|shuffl\w*|leak\w*|autocorrel\w*|temporal\w*\s+"
               r"(?:autocorr|dependen|correlat)|run[\s-]?block\w*|leave[\s-]?one[\s-]?run|"
               r"block\w*\s+by\s+run|within[\s-]?run|group\w*\s+by\s+run|non[\s-]?independen\w*")
    downgrade = [
        r"(?:random|shuffl\w*|k-?\s*fold|non[\s-]?block\w*|non[\s-]?run[\s-]?block\w*)"
        r"(?:(?!" + _NEG + r").){0,55}?(?:inflat\w*|leak\w*|over-?estimat\w*|over-?stat\w*|"
        r"optimistic|too high|higher|larger|biased?|invalid|not valid|artifact|spuriou\w*)",
        r"(?:inflat\w*|leak\w*|over-?estimat\w*|over-?stat\w*|optimistic|biased?|artifact|spuriou\w*)"
        r"(?:(?!" + _NEG + r").){0,55}?(?:random|shuffl\w*|k-?\s*fold|autocorr\w*|within[\s-]?run|"
        r"temporal|not block\w*|non[\s-]?block\w*|same run)",
        r"(?:run[\s-]?block\w*|leave[\s-]?one[\s-]?run|block\w*\s+by\s+run|group\w*\s+by\s+run)"
        r"(?:(?!" + _NEG + r").){0,45}?(?:valid|correct|honest|proper|unbiased?|avoid\w*|prevent\w*|"
        r"remov\w*|only|must|should|required?|the\s+result|the\s+accuracy|~?\s*0\.6)",
        r"(?:accuracy|decoding|result|estimate|performance|number)"
        r"(?:(?!" + _NEG + r").){0,45}?(?:depend\w*|inflat\w*|hinge\w*|driven|artifact|determined)"
        r"(?:(?!" + _NEG + r").){0,45}?(?:cross[\s-]?validat\w*|\bcv\b|split|scheme|fold|block\w*)",
        r"(?:autocorrel\w*|adjacent|near[\s-]?duplicate|temporal\w*|same run)"
        r"(?:(?!" + _NEG + r").){0,55}?(?:train|test|fold|leak\w*|split|both)",
    ]
    absence = [
        r"must (?:be )?block\w*(?:\s+the\s+\w+)?\s+by\s+run",
        r"only (?:the )?run[\s-]?block\w*[^.\n]{0,25}(?:estimate|accuracy|result|valid)",
        r"(?:not|isn'?t)\s+(?:a\s+)?valid[^.\n]{0,30}(?:random|shuffl\w*|k-?\s*fold|non[\s-]?block)",
    ]
    return bool(re.search(concept, text, re.I)) and (
        any(_unnegated(text, p) for p in downgrade) or any(re.search(p, text, re.I) for p in absence))


def _labelled_run_blocked(blobs, text):
    """The agent documents a run-blocked / leave-one-run-out CV scheme (in JSON string values or in
    findings.md prose)."""
    for obj in blobs.values():
        found = []

        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
            elif isinstance(o, str):
                found.append(o)

        walk(obj)
        if any(_RUNBLOCK.search(s) for s in found):
            return True
    return bool(_RUNBLOCK.search(text))


def test_cross_validation_run_blocked():
    """The valid run-blocked 8-way accuracy on these data is ~0.63; a headline near ~0.9 is the
    signature of a random / shuffled k-fold CV that leaks temporally-autocorrelated adjacent volumes
    across train/test on blocked fMRI runs. Requires (a) the headline accuracy is NOT inflated
    (<= 0.80), and (b) run-blocking is evidenced — the emitted CV folds are genuinely run-blocked
    (no run crosses train/test), OR findings.md recognises the leakage, OR the CV scheme is labelled
    run-blocked. If CV folds ARE emitted, they must genuinely be run-blocked (a fabricated leaky-fold
    structure fails)."""
    blobs = _blobs()
    assert blobs, "no *.json output found (empty submission)"

    acc = _headline_accuracy(blobs)
    assert acc is not None, "no decoding accuracy found in any *.json output"

    # (b') If the agent emitted an explicit CV-fold structure, it must actually be run-blocked:
    # every held-out test run must be absent from that fold's training runs (validated from the run
    # ids, not a self-reported flag). A fabricated leaky-fold structure fails here.
    folds = _cv_folds(blobs)
    folds_ok = _folds_run_blocked(folds)
    if folds:
        assert folds_ok, (
            "the emitted cross-validation folds are NOT run-blocked: at least one run appears in "
            "both the training and test set of a fold, which leaks temporally-autocorrelated "
            "within-run volumes across train/test. Hold out one entire run per fold (leave-one-run-out).")

    # (a) headline must not be inflated by within-run temporal leakage
    assert acc <= LEAK_FLOOR, (
        f"reported 8-way decoding accuracy {acc:.3f} is in the range produced by random k-fold "
        f"cross-validation, which leaks temporally-autocorrelated adjacent volumes across train/test "
        f"on blocked fMRI runs. The run-blocked (leave-one-run-out) accuracy on these data is ~0.63; "
        f"a value near 0.9 means the cross-validation was not blocked by run and is inflated.")

    # (b) run-blocking must be evidenced
    text = _findings()
    evidenced = folds_ok or _recognises_cv_leakage(text) or _labelled_run_blocked(blobs, text)
    assert evidenced, (
        "the reported accuracy is not inflated, but the submission does not evidence run-blocked "
        "cross-validation: emit the leave-one-run-out fold structure (held-out run absent from the "
        "training runs), label the CV scheme as run-blocked, or state in findings.md that a random "
        "k-fold CV inflates the accuracy via within-run temporal leakage and that the valid estimate "
        "blocks the cross-validation by run.")
