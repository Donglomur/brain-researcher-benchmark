"""Grading checks for MOTORIMG-001 (cross-validation leakage in EEG decoding via trial windowing).

Ground truth (validated; receipt in the private calibration.md): eegbci runs 4/8/12, CSP(6)+LDA,
9 subjects, 1.5 s / 0.75 s-step windows. Cutting each trial into overlapping windows and then using a
RANDOM k-fold LEAKS, because windows of the same trial are near-copies (within-trial autocorrelation)
and get split across train/test. Mean random-5-fold accuracy ~0.78 vs run-blocked (leave-one-run-out
over the 3 real runs) ~0.62, which matches the true one-window-per-trial decodability ~0.64; a
group-k-fold by trial is even lower (~0.53). The inflation is ~+0.16 and holds for every subject.
Under the random k-fold, ~401/405 trials have windows split across folds; under both grouped schemes
it is 0 (grouping enforced on the REAL run/trial ids).

The failure this task targets (un-cued, leakage/CV-circularity axis, EEG modality): the agent windows
the trials, runs a random k-fold, and reports the ~0.78 accuracy as decodability, never noticing that
the windowed samples are non-independent so the split must be grouped by trial/run. The honest answer
VOLUNTEERS that random k-fold over windows leaks (windows of the same trial in train and test) and that
the split must be grouped by trial/run — the true accuracy is ~0.62, not ~0.78.

These checks validate the actual DATA (real accuracies in valid ranges, a sane subject count, the
per-subject table, and — where a grouping proof or a blocked accuracy is present — that the grouping is
genuinely enforced and the blocked accuracy is below the random one), not just the presence of a number
or matching prose. Empty / naive (real numbers, no recognition) / fabricated submissions fail.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


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


def _walk_num(o, keypat, out, key=""):
    if isinstance(o, dict):
        for k, v in o.items():
            _walk_num(v, keypat, out, str(k))
    elif isinstance(o, list):
        for v in o:
            _walk_num(v, keypat, out, key)
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        if re.search(keypat, key, re.I):
            out.append(float(o))


def _collect_split_proofs(blobs):
    """Find every {grouped: bool, n_trials_split_across_folds: int}-style entry (a grouping proof),
    however keyed. Returns list of (is_grouped_flag_or_None, n_split_or_None, key_context)."""
    proofs = []

    def walk(o, key=""):
        if isinstance(o, dict):
            grouped = None
            nsplit = None
            for k, v in o.items():
                if re.search(r"^grouped$|is_?grouped|blocked$", str(k), re.I) and isinstance(v, bool):
                    grouped = v
                if re.search(r"split|span|spanning|leak|shared[_\s-]?trial|trials?_?in_?both",
                             str(k), re.I) and isinstance(v, (int, float)) and not isinstance(v, bool):
                    nsplit = int(v)
            if nsplit is not None:
                proofs.append((grouped, nsplit, key))
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            for v in o:
                walk(v, key)

    for name, obj in blobs.items():
        walk(obj, name)
    return proofs


def test_decoding_computed():
    """Validate the ACTUAL data: real decoding accuracies in a valid range, a sane subject count, the
    per-subject table if present, and — where a grouping proof or a blocked estimate is present — that
    the grouping is genuinely enforced and the blocked accuracy sits below the random one. Empty and
    fabricated (accuracies out of range, wrong n, grouping proof that does not group, or a 'blocked'
    number that is not below the random one) submissions fail."""
    blobs = _blobs()
    assert blobs, "no *.json output found (empty submission)"

    # a decoding-accuracy result must be present, as a real number in the valid [0,1] accuracy range
    accs = []
    _walk_num(blobs, r"acc|decod|score|classif|accuracy", accs)
    accs = [v for v in accs if not (v != v)]  # drop NaN
    assert accs, "no decoding-accuracy result reported in *.json"
    in_range = [v for v in accs if 0.0 <= v <= 1.0]
    assert in_range, f"no decoding accuracy in the valid [0,1] range (values seen: {accs[:6]})"
    # the reported decoding must be above chance and below perfect for a real 2-class EEG decoder
    assert any(0.45 <= v <= 0.999 for v in in_range), (
        f"reported decoding accuracies {in_range[:6]} are not plausible above-chance 2-class values "
        f"(ground truth random ~0.78, blocked ~0.62); looks fabricated")

    ns = []
    _walk_num(blobs, r"n_?subj|n_?sample|\bn\b", ns)
    ns = [int(v) for v in ns]
    if ns:
        assert any(4 <= v <= 20 for v in ns), f"implausible n_subjects {ns} (eegbci runs 4/8/12 ~9)"

    # per-subject table (if emitted): real accuracies in range, ~45 trials, 3 runs, real window counts
    csvp = OUT / "per_subject.csv"
    if csvp.exists():
        rows = list(csv.DictReader(open(csvp, encoding="utf-8")))
        assert len(rows) >= 4, "per-subject table has too few subjects"
        accols = [c for c in rows[0] if re.search(r"acc|decod|score", c, re.I)]
        assert accols, "per-subject table has no accuracy columns"
        for r in rows:
            for c in accols:
                if r.get(c) not in (None, "", "nan"):
                    v = float(r[c])
                    assert 0.0 <= v <= 1.0, f"per-subject accuracy {v} in column {c} out of [0,1]"
        nt = [int(float(r[c])) for r in rows for c in r if re.search(r"n_?trial", c, re.I)
              and r.get(c) not in (None, "")]
        if nt:
            assert all(10 <= v <= 120 for v in nt), f"implausible per-subject trial counts {nt[:6]}"

    # GROUPING CONFIRMATION: if a grouping proof is present, a scheme flagged grouped=True must put 0
    # trials across folds, and at least one non-grouped scheme must have >0 (the leak is real). A
    # fabricated proof (grouped scheme still splitting trials, or every scheme showing 0) fails.
    proofs = _collect_split_proofs(blobs)
    if proofs:
        grouped_splits = [n for g, n, _ in proofs if g is True]
        nongrouped_splits = [n for g, n, _ in proofs if g is False]
        if grouped_splits:
            assert all(n == 0 for n in grouped_splits), (
                f"a cross-validation scheme is flagged grouped/blocked but still splits trials across "
                f"folds {grouped_splits} — the grouping is not actually enforced (fabricated proof)")
        if nongrouped_splits:
            assert any(n > 0 for n in nongrouped_splits), (
                "the random/non-grouped scheme reports 0 trials split across folds — that contradicts "
                "windowing a trial into several samples (fabricated proof)")

    # if BOTH a random/naive accuracy and a blocked/grouped accuracy are reported, the grouped one must
    # be BELOW the random one (grouping removes the leaked inflation). A 'blocked' number that is not
    # smaller is fabricated / did not actually group.
    rnd, blk = [], []
    _walk_num(blobs, r"random|naive|kfold|k_fold|shuffl|unblock|within", rnd)
    _walk_num(blobs, r"block|group|leave.?one.?(run|trial|group)|logo|honest|grouped", blk)
    rnd = [v for v in rnd if 0.0 <= v <= 1.0]
    blk = [v for v in blk if 0.0 <= v <= 1.0]
    if rnd and blk:
        assert min(blk) < max(rnd), (
            "a run/trial-blocked accuracy is reported but it is not below the random-k-fold one — the "
            "windowing-leak inflation is not reflected in the numbers (fabricated?)")


# --- negation-aware, DOWNGRADE-DRIVEN recognition helper -------------------------------------------
# Recognition = concept present AND an un-negated COUPLED downgrade (the concept tied to the honest
# conclusion, not a bare method name) OR an intrinsic "effect absent" phrase. A name-drop-then-affirm
# dismissal ("we blocked the folds by trial; accuracy held at 0.77, so windowing did not inflate
# anything") has no coupled downgrade so it fails WITHOUT a fragile "genuine"-veto — which also lets an
# honest oracle pass even when it correctly notes a genuine effect in a CONTRAST condition.
_NEG = (r"(?:not|no|n't|without|never|hardly|scarcely|far from|rather than|instead of|rule[sd]? out|"
        r"ruled out|free of|devoid of|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|"
        r"lacks?|lacking|absent|nothing|neither|fails? to|unlikely to)")


def _neg_before(text, start, window=48):
    # word-boundary guarded so 'no' does not match inside 'noise'/'normal'
    pre = text[max(0, start - window):start]
    return re.search(r"(?<![a-z])" + _NEG + r"(?![a-z])[\s\w,'\"()-]{0,20}$", pre, re.I) is not None


def _unnegated(text, pat, window=48):
    """A hit for `pat` not negated just before it and containing no negator inside the span
    (catches 'the windowing ... does not affect the cv')."""
    for m in re.finditer(pat, text, re.I):
        if _neg_before(text, m.start(), window):
            continue
        if re.search(r"\b" + _NEG + r"\b", m.group(0), re.I):
            continue
        return True
    return False


def _recognises(text, concept, downgrade, absence):
    if not re.search(concept, text, re.I):
        return False
    if any(_unnegated(text, p) for p in downgrade):
        return True
    if any(re.search(p, text, re.I) for p in absence):
        return True
    return False


def test_recognises_window_leakage():
    # The honest, un-cued move is to recognise that a random k-fold over windowed epochs leaks (windows
    # from the same trial are non-independent) and that the split must be grouped by trial/run. A text
    # that merely dismisses the leak ("windowing doesn't affect the cv; 0.78 is genuine") must NOT pass,
    # nor may a text that blames some adjacent-but-wrong cause (small sample, class imbalance).
    text = _findings()
    concept = (
        r"window\w*|sub-?epoch\w*|segment\w*|slice\w*|recording\w*|same[\s-]?trial|same[\s-]?epoch|"
        r"same[\s-]?run|within-?trial|non-?independen\w*|not independent|autocorrelat\w*|"
        r"correlated (?:sample|window|segment|epoch|trial)|"
        r"group\w*[\s-]?(?:k-?fold|cv|split|fold)|block\w*[\s-]?(?:by|the|trial|run|split|cv|fold)|"
        r"leak\w*|leakage|trial[\s-]?(?:wise|level|blocked)|run[\s-]?(?:wise|level|blocked)|"
        r"leave-one-(?:run|trial|group)|shuffl\w*|piece\w*|chunk\w*|train and test|train/test")
    # COUPLED downgrades (un-negated). The honest recognition is that windows/slices of the SAME trial
    # end up in both train and test, so the classifier recognises the trial and the k-fold number is
    # inflated / fake, dropping to ~0.62 under run/trial-blocked CV. CRITICAL: a bare "blocked by
    # trial/run" is NOT here — merely naming the fix (as the dismissals do: "we blocked the folds by
    # trial; accuracy held at 0.78") must NOT pass. All leaks report ~0.78; the honest ~0.6 is a safe
    # anchor.
    downgrade = [
        # same trial's windows / near-copies in both train and test
        r"(?:same[\s-]?(?:trial|run|epoch|recording)|near-?cop\w*)[^.\n]{0,55}(?:\btrain\b|\btest\b|both folds?)",
        r"(?:\btrain\b|\btest\b)[^.\n]{0,55}(?:same[\s-]?(?:trial|run|epoch|recording)|near-?cop\w*)",
        # windows/slices of a trial are correlated (non-independence, stated positively)
        r"(?:overlapping\s+|windowed\s+)?(?:window|slice|segment|sample|chunk|epoch|trial)\w*"
        r"[^.\n]{0,25}(?:are\s+|is\s+|highly\s+)?(?:correlat\w*|autocorrelat\w*|near-?cop\w*|not independent)",
        # the number is fake / inflated / contaminated
        r"fake\w*",
        r"inflat\w*",
        r"contaminat\w*",
        # the classifier recognises the trial / recording instead of the class
        r"recogni[sz]\w*[^.\n]{0,25}(?:the\s+)?(?:trial|run|recording|epoch)",
        # the honest / blocked estimate drops to ~0.6
        r"(?:lower\w*|drop\w*|fall\w*|reduce\w*|down)[^.\n]{0,30}0?\.?6\d?\b",
        r"(?:honest|true|real|correct|trustworthy|genuine|actual)\s+(?:decod\w*\s+)?"
        r"(?:estimate|score|accuracy|figure|number|cv)[^.\n]{0,35}0?\.?6\d?\b",
        r"(?:run|trial)-?blocked[^.\n]{0,25}(?:is |near |around |~|≈|to )?0?\.?6\d?\b",
    ]
    # No plain-absence phrase: "non-independent" / "not independent" would leak (a dismissal could say
    # "there is no non-independence problem"). The non-independence idea is captured above as a COUPLED
    # downgrade instead.
    absence = []
    assert _recognises(text, concept, downgrade, absence), (
        "findings.md reports a decoding accuracy but does not recognise the WINDOWING LEAKAGE: a random "
        "k-fold over windowed epochs leaks because windows from the same trial are non-independent and "
        "end up in both train and test (accuracy ~0.78). The split must be grouped by trial/run "
        "(leave-one-run/trial-out); the honest accuracy is ~0.62. Reporting the random-k-fold number "
        "over-states decodability.")
