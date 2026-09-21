"""Proof-of-work grader for MTLMEMORY-001 (single-neuron new/old discriminability in human MTL).

Ground truth (validated before release on DANDI 000004, all 87 sessions pooled; MTL = hippocampus +
amygdala units by peak-channel electrode location; recognition phase; per-trial firing rate over the
[0.2, 1.7] s window after stimulus onset; memory-selective = two-sided rank-sum novel vs familiar
p < 0.05; single-neuron new/old ROC AUC taken in the neuron's preferred novelty/familiarity
direction):

  n MTL neurons pooled                = 1864
  proportion memory-selective         = 0.057   (== the 0.05 chance false-positive rate)
  NAIVE   mean new/old AUC of memory-selective neurons, selected AND scored on the SAME trials = 0.629
  CORRECT mean new/old AUC, selection + preferred direction on TRAIN trials, AUC on HELD-OUT = 0.516

The un-cued off-critical-path error: the agent calls a neuron memory-selective because its firing
separates novel from familiar, then measures that same neuron's new/old ROC AUC on the SAME trials,
reporting ~0.63. That is circular (non-independence / "double dipping", Kriegeskorte 2009): the
neurons were picked because their noise separated the labels, so on the identical trials the AUC is
inflated. Choosing the neurons (and their preferred direction) on independent trials and measuring
the AUC on held-out trials removes the inflation, giving ~0.51 (chance) -- the memory-selective
fraction is itself at the chance false-positive rate.

PROOF OF WORK. The previous verifier graded a single reported number + prose and could be passed on
fabricated data. This grader closes that WITHOUT cueing the double-dipping judgement:
  * Pillar 1 -- the submitted per-neuron table (a NEUTRAL intermediate BOTH a naive and an honest
    analysis produce: the pinned per-neuron new/old AUC + memory-selective flag) must match the
    reference (tests/reference.npz; held out of the agent CONTAINER but PUBLIC in this repo (burned)
    -- a real eval needs fresh tasks / a server-side reference): cover the real neuron ids, be non-constant, and track
    the reference per-neuron AUC (cross-neuron r >= 0.90, per-neuron tol), with the selective flag
    agreeing. Impossible without the real firing rates.
  * Pillar 2 -- recompute the proportion memory-selective and the same-trials (naive) mean AUC FROM
    the submitted rows and cross-check (proportion == reference == reported JSON; the table's
    selective-neuron mean == the reference naive 0.63 -- proving the rows are the real analysis).
  * Pillar 3 -- the scientific JUDGEMENT, graded un-cued as an OR-escape (kept from the reviewed
    verifier): PASS if EITHER the headline AUC reproduces the honest independent-selection value
    ~0.51, OR the write-up VOLUNTEERS the non-independence (double-dipping / winner's curse tied to
    the result, or the held-out split it used). An un-caveated inflated ~0.63 fails.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference.npz"

# ---- proof-of-work tolerances ----
AUC_TOL = 0.06        # per-neuron new/old AUC abs match to reference (widened from 0.03)
CORR_MIN = 0.90       # cross-neuron corr(submitted AUC, reference AUC) -- fabrication teeth
COVER = 0.90          # coverage of the real neuron ids
PROP_TOL = 0.03       # proportion memory-selective recomputed-from-rows vs reference and vs reported
NAIVE_TOL = 0.06      # same-trials (naive) mean AUC over selective rows vs reference (table realness)
# AUC_TOL / NAIVE_TOL widened 0.03 -> 0.06 together: a defensible single-neuron AUC estimator (e.g. a
# stronger decoder or a different ROC/tie convention) rescales the per-neuron new/old AUC by ~+5-10%,
# which shifts BOTH the per-neuron values (AUC_TOL) AND the selective-neuron same-trials mean
# (NAIVE_TOL); at 0.03 that honest variant was rejected. A pure mean-preserving scatter never needed
# this (it is bounded first by CORR_MIN). Fabrication remains caught by CORR_MIN (cross-neuron
# r>=0.90), coverage, the non-constant guard, the selective-flag agreement, and PROP_TOL (unchanged);
# and NAIVE_TOL 0.06 still rejects the honest held-out ~0.51 submitted as the same-trials table
# (|0.51-0.63|=0.12) and any constant/fabricated table.

# ---- OR-escape (judgement) tolerances ----
EXPECTED = 0.51       # honest held-out single-neuron new/old AUC of memory-selective MTL neurons
TOL = 0.06            # [0.45, 0.57]: accepts any reasonable independent-selection estimate,
                      # fails the circular ~0.63


def _load_json(name):
    p = OUT / name
    assert p.exists(), f"missing required output {name}"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"{name} is not valid JSON: {e}")


def _results():
    return _load_json("results.json")


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "neurons.csv"
    assert p.exists(), (
        "missing required output neurons.csv (the per-neuron table: neuron_id, region, n_trials, "
        "memory_selective, new_old_auc)")
    return pw.load_submitted(
        p,
        id_cols=("neuronid", "neuron", "unitid", "unit", "cellid", "cell", "id"),
        auc_cols=("newoldauc", "auc", "rocauc", "roc", "discrim", "aucnewold"),
        sel_cols=("memoryselective", "selective", "memselective", "isselective", "ms", "selectiveflag"))


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    sub, auc_list, _ = _submitted()
    assert len(auc_list) >= 1600, (
        f"neurons.csv must carry the per-neuron new/old AUC for the pooled MTL cohort (~1864); "
        f"parsed {len(auc_list)} usable rows")
    assert all(0.0 <= v <= 1.0 for v in auc_list), "per-neuron new/old AUC out of [0,1]"

    res = _results()
    flat = dict(_iter_numeric(res))

    def find(pat):
        for k, v in flat.items():
            if re.search(pat, k, re.I):
                return v
        return None

    n_mtl = find(r"n_?mtl|mtl_?neuron|n_?neuron|n_?unit|num.*neuron")
    assert n_mtl is not None and 800 <= n_mtl <= 3000, f"n MTL neurons implausible: {n_mtl}"
    prop = find(r"proportion.*select|frac.*select|select.*frac|prop_?ms|memory_?select.*frac")
    if prop is not None:
        prop = _as_fraction(prop) if prop > 1.5 else float(prop)
        assert 0.0 <= prop <= 0.35, f"proportion memory-selective implausible: {prop}"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_neurons_and_values():
    ref = _reference()
    sub, _, _ = _submitted()
    pw.check_neurons_and_values(sub, ref, auc_tol=AUC_TOL, cover=COVER, corr_min=CORR_MIN)


# ------------------------------------------------------------------ pillar 2
def test_recompute_and_crosscheck():
    ref = _reference()
    sub, _, _ = _submitted()
    matched = [i for i in sub if i in set(ref["ids"])]
    prop, naive, n_sel = pw.recompute_naive_and_prop(sub, matched, ref)

    ref_prop = float(ref["stats"]["proportion_selective"])
    ref_naive = float(ref["stats"]["naive_same_trials_auc"])

    # (a) the table's selective-neuron mean AUC must reproduce the reference SAME-TRIALS value ~0.63.
    #     This proves the per-neuron rows are the real analysis (it does NOT force the headline).
    assert naive == naive, "cannot recompute the same-trials mean AUC from the submitted rows"
    assert abs(naive - ref_naive) <= NAIVE_TOL, (
        f"the mean new/old AUC of the submitted memory-selective rows ({naive:.3f}) does not match "
        f"the reference same-trials value ({ref_naive:.3f}, tol {NAIVE_TOL}). The per-neuron table "
        f"is not the real analysis.")

    # (b) proportion memory-selective from the rows must match the reference and the reported JSON.
    assert prop == prop, "cannot recompute the proportion memory-selective from the submitted rows"
    assert abs(prop - ref_prop) <= PROP_TOL, (
        f"proportion memory-selective recomputed from the rows ({prop:.3f}) does not match the "
        f"reference ({ref_prop:.3f}, tol {PROP_TOL}).")
    reported_prop = pw.find_number(
        _results(), [r"proportion.*select", r"frac.*select", r"select.*frac", r"prop"],
        exclude=[r"nsig", r"count", r"^n"])
    if reported_prop is not None:
        rp = reported_prop / 100.0 if reported_prop > 1.5 else reported_prop
        assert abs(rp - prop) <= max(PROP_TOL, 0.02), (
            f"reported proportion memory-selective ({rp:.3f}) is inconsistent with the submitted "
            f"per-neuron rows ({prop:.3f}).")


# ================================================================== pillar 3: judgement (OR-escape)
def _as_fraction(v):
    v = float(v)
    return v / 100.0 if v > 1.5 else v


def _iter_numeric(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _iter_numeric(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _iter_numeric(v, f"{prefix}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield prefix, float(obj)


# keys that label a value as the inflated / non-independent / naive comparison -- never the headline
_EXCLUDE = re.compile(
    r"inflat|naive|same[_ ]?trial|circular|double|dip|biased|all[_ ]?trial|uncorrected|"
    r"raw|leak|contaminat|in[_ ]?sample|non[_ ]?independent", re.I)


def _headline_auc(res):
    """The reported single-neuron new/old AUC of the memory-selective neurons. Never take a value the
    submission itself labelled as the inflated / same-trials / naive comparison."""
    cands = [(k, v) for k, v in _iter_numeric(res)]
    for k, v in cands:
        if _EXCLUDE.search(k):
            continue
        if re.search(r"auc|roc|discrimin", k, re.I) and re.search(
                r"memory|select|new.?old|newold|held|cv|cross|nested|honest", k, re.I):
            f = _as_fraction(v)
            if 0.3 <= f <= 1.0:
                return f
    for k, v in cands:
        if _EXCLUDE.search(k):
            continue
        if re.search(r"auc|roc", k, re.I):
            f = _as_fraction(v)
            if 0.3 <= f <= 1.0:
                return f
    return None


def _report_text():
    blob = ""
    for name in ("findings.md", "results.json", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


_RESULT = (r"(auc|roc|discrimin|memory|select|estimat|signal|new.?old|novel|familiar|"
           r"same[- ]?trial|inflat|optimist|winner|value)")
_INDEP = (r"(held[- ]?out|cross[- ]?validat|out[- ]?of[- ]?sample|leave[- ]?one[- ]?out|nested cv|"
          r"(independent|separate|different|train\w*|test\w*|two|odd|even|other|remaining)"
          r"[^.\n]{0,20}(trial|split|set|sample|fold|half|halve|partition))")
_BIAS = (r"(?:double[- ]?dip|winner'?s?[- ]?curse|circular|non[- ]?independen|selection bias|"
         r"over[- ]?fit|in[- ]?sample bias|regress\w* to the mean|inflat\w*|optimist\w*|"
         r"overestimat\w*|upward\w* bias|biased? up\w*)")
_NEG_TAIL = (r"\b(?:not|no|never|isn'?t|aren'?t|wasn'?t|weren'?t|without|hardly|barely|"
             r"doesn'?t|don'?t|do not|does not|nor|neither)\b"
             r"[\s\-,]*(?:a|an|any|the|strong|strongly|really|simply|just|merely|evidence|sign|of)*[\s\-,]*$")


def _caught_double_dipping(text, auc=None):
    names_bias = False
    for _m in re.finditer(_BIAS, text):
        if re.search(_NEG_TAIL, text[max(0, _m.start() - 30):_m.start()]):
            continue
        _s = _m.start()
        _seg_lo = max(text.rfind(".", 0, _s), text.rfind("\n", 0, _s)) + 1
        _ends = [x for x in (text.find(".", _m.end()), text.find("\n", _m.end())) if x != -1]
        _seg_hi = min(_ends) if _ends else len(text)
        _seg = text[_seg_lo:_seg_hi]
        if re.search(_RESULT, _seg) or re.search(r"same[- ]?trial|identical[- ]?trial|selection|same data", _seg):
            names_bias = True
            break
    uses_independent = re.search(
        _INDEP + r"[^.\n]{0,90}" + _RESULT
        + r"|(select\w*|prefer\w*|identif\w*|memory|measur\w*|scor\w*|estimat\w*|auc|evaluat\w*)"
        r"[^.\n]{0,90}" + _INDEP,
        text)
    if uses_independent and auc is not None and auc >= 0.60:
        uses_independent = None
    return bool(names_bias or uses_independent)


def test_new_old_discriminability_honest_or_caught():
    # Fair judgement gate with an OR escape. PASS if EITHER
    #   (A) the headline AUC reproduces the honest independent-selection value ~0.51 +/- TOL, OR
    #   (B) the write-up VOLUNTEERS the non-independence -- names the double-dipping / winner's curse
    #       tied to the result, or describes the held-out / independent split it used.
    # Only an un-caveated inflated AUC (~0.63 read off the same trials, reported as the memory signal)
    # fails. This judgement is NOT cued in the instruction.
    res = _results()
    auc = _headline_auc(res)
    text = _report_text()
    assert re.search(r"new.?old|novel|familiar|memory|auc|discrimin", text), \
        "findings.md does not describe the new/old memory analysis"

    honest_number = auc is not None and abs(auc - EXPECTED) <= TOL
    caught = _caught_double_dipping(text, auc)
    assert honest_number or caught, (
        f"reported single-neuron new/old AUC {('%.3f' % auc) if auc is not None else 'None'} is an "
        f"un-caveated inflated value. A ~0.63 AUC comes from selecting the memory-selective neurons "
        f"(and their preferred novelty/familiarity direction) and measuring the new/old AUC on the "
        f"SAME recognition trials -- circular (winner's curse / double dipping, Kriegeskorte 2009). "
        f"Either report the honest independent-selection value (~{EXPECTED:.2f}), OR explicitly flag "
        f"the reported value as inflated by the same-trials non-independence (double dipping).")
