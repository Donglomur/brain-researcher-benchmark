"""Proof-of-work grader for VISCAT-001 (single-neuron visual-category selectivity in human MTL).

Ground truth (validated before release on DANDI 000004, all 87 sessions pooled; MTL = hippocampus +
amygdala units by peak-channel electrode location; recognition phase; per-trial firing rate over the
[0.2, 1.7] s window after stimulus onset; category-selective = Kruskal-Wallis across the five visual
categories p < 0.05; preferred category = highest mean firing; preferred-category-vs-rest ROC AUC):

  n MTL neurons pooled                 = 1864
  proportion category-selective        = 0.167   (well above the 0.05 chance false-positive rate)
  NAIVE   mean preferred-vs-rest AUC, selected AND scored on the SAME trials             = 0.695
  CORRECT mean preferred-vs-rest AUC, selection + preferred category on TRAIN, AUC on HELD-OUT = 0.570

The un-cued off-critical-path error: the agent calls a neuron category-selective and picks its
preferred category (highest-firing of five) on a set of trials, then measures the
preferred-category-vs-rest AUC on the SAME trials, reporting ~0.70. That is circular (double dipping,
Kriegeskorte 2009): among five categories the preferred one is chosen because its firing was highest
on those trials. Choosing the neurons + preferred category on independent trials and measuring the
AUC on held-out trials gives ~0.57 -- a GENUINE positive effect (visual-category selectivity is real)
but materially smaller than the same-trials estimate.

PROOF OF WORK (fabrication-proof, judgement kept un-cued):
  * Pillar 1 -- the submitted per-neuron table (NEUTRAL: the pinned per-neuron preferred-vs-rest AUC +
    category-selective flag, an intermediate BOTH a naive and an honest analysis produce) must match
    the reference (tests/reference.npz; held out of the agent CONTAINER but PUBLIC in this repo
    (burned) -- a real eval needs fresh tasks / a server-side reference): cover the real neuron ids,
    be non-constant, track the reference per-neuron AUC (cross-neuron r >= 0.90, per-neuron tol),
    selective flag agreeing.
  * Pillar 2 -- recompute the proportion category-selective and the same-trials (naive) mean AUC FROM
    the submitted rows and cross-check (proportion == reference == reported; selective-neuron mean ==
    the reference naive 0.695 -- proving the rows are the real analysis).
  * Pillar 3 -- the scientific JUDGEMENT, graded un-cued as an OR-escape: PASS if EITHER the headline
    preferred-vs-rest AUC reproduces the honest ~0.57, OR the write-up VOLUNTEERS the non-independence
    (double dipping / winner's curse tied to the AUC, or the held-out split it used). An un-caveated
    inflated ~0.70 fails.
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
AUC_TOL = 0.06        # per-neuron pref-vs-rest AUC abs match (widened from 0.03). The reference AUC
                      # spread is wide (std 0.064), so a defensible mean-preserving decoder variant
                      # (a different single-neuron AUC estimator) at the CORR_MIN corr floor (~0.90)
                      # has ~0.031 per-neuron residual -- only ~67-76% within 0.03, so 0.03 rejected
                      # an honest variant even though it preserved the selective-neuron mean. Widening
                      # AUC_TOL alone rescues it; fabrication stays caught by CORR_MIN (r>=0.90 -- a
                      # shuffled table fails), coverage, the non-constant guard, selective-flag
                      # agreement, and the UNCHANGED NAIVE_TOL (a mean-preserving variant passes it,
                      # a constant/shifted table does not).
CORR_MIN = 0.90
COVER = 0.90
PROP_TOL = 0.04       # proportion category-selective (ref ~0.167)
NAIVE_TOL = 0.03      # same-trials (naive) mean AUC over selective rows vs reference (0.695)

# ---- OR-escape (judgement) tolerances ----
EXPECTED = 0.575      # honest held-out single-neuron preferred-vs-rest AUC of category-selective cells
TOL = 0.055           # [0.52, 0.63]: accepts any reasonable independent-selection estimate,
                      # fails the circular same-trials value (~0.70)
INFLATED_GUARD = 0.63  # a claimed held-out split cannot rescue a headline this high


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
        "category_selective, pref_vs_rest_auc)")
    return pw.load_submitted(
        p,
        id_cols=("neuronid", "neuron", "unitid", "unit", "cellid", "cell", "id"),
        auc_cols=("prefvsrestauc", "prefvsrest", "preferredauc", "categoryauc", "auc", "rocauc", "roc"),
        sel_cols=("categoryselective", "catselective", "selective", "isselective", "sel", "selectiveflag"))


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    sub, auc_list, _ = _submitted()
    assert len(auc_list) >= 1600, (
        f"neurons.csv must carry the per-neuron preferred-vs-rest AUC for the pooled MTL cohort "
        f"(~1864); parsed {len(auc_list)} usable rows")
    assert all(0.0 <= v <= 1.0 for v in auc_list), "per-neuron preferred-vs-rest AUC out of [0,1]"

    res = _results()
    flat = dict(_iter_numeric(res))

    def find(pat):
        for k, v in flat.items():
            if re.search(pat, k, re.I):
                return v
        return None

    n_mtl = find(r"n_?mtl|mtl_?neuron|n_?neuron|n_?unit|num.*neuron")
    assert n_mtl is not None and 800 <= n_mtl <= 3000, f"n MTL neurons implausible: {n_mtl}"
    prop = find(r"proportion.*select|frac.*select|select.*frac|prop_?sel|categor.*select.*frac")
    if prop is not None:
        prop = _as_fraction(prop) if prop > 1.5 else float(prop)
        assert 0.03 <= prop <= 0.6, f"proportion category-selective implausible: {prop}"


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

    assert naive == naive, "cannot recompute the same-trials mean AUC from the submitted rows"
    assert abs(naive - ref_naive) <= NAIVE_TOL, (
        f"the mean preferred-vs-rest AUC of the submitted category-selective rows ({naive:.3f}) does "
        f"not match the reference same-trials value ({ref_naive:.3f}, tol {NAIVE_TOL}). The per-neuron "
        f"table is not the real analysis.")

    assert prop == prop, "cannot recompute the proportion category-selective from the submitted rows"
    assert abs(prop - ref_prop) <= PROP_TOL, (
        f"proportion category-selective recomputed from the rows ({prop:.3f}) does not match the "
        f"reference ({ref_prop:.3f}, tol {PROP_TOL}).")
    reported_prop = pw.find_number(
        _results(), [r"proportion.*select", r"frac.*select", r"select.*frac", r"prop"],
        exclude=[r"nsig", r"count", r"^n"])
    if reported_prop is not None:
        rp = reported_prop / 100.0 if reported_prop > 1.5 else reported_prop
        assert abs(rp - prop) <= max(PROP_TOL, 0.02), (
            f"reported proportion category-selective ({rp:.3f}) is inconsistent with the submitted "
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


_EXCLUDE = re.compile(
    r"inflat|naive|same[_ ]?trial|circular|double|dip|biased|all[_ ]?trial|uncorrected|"
    r"raw|leak|contaminat|in[_ ]?sample|non[_ ]?independent", re.I)


def _headline_auc(res):
    cands = [(k, v) for k, v in _iter_numeric(res)]
    for k, v in cands:
        if _EXCLUDE.search(k):
            continue
        if re.search(r"auc|roc|discrimin", k, re.I) and re.search(
                r"categor|select|prefer|pref|held|cv|cross|nested|honest", k, re.I):
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


_RESULT = (r"(auc|roc|discrimin|prefer|select|estimat|signal|categor|"
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
        if re.search(_RESULT, _seg) or re.search(
                r"same[- ]?trial|identical[- ]?trial|selection|preferred categor|same data", _seg):
            names_bias = True
            break
    uses_independent = re.search(
        _INDEP + r"[^.\n]{0,90}" + _RESULT
        + r"|(select\w*|prefer\w*|identif\w*|categor\w*|measur\w*|scor\w*|estimat\w*|auc|evaluat\w*)"
        r"[^.\n]{0,90}" + _INDEP,
        text)
    if uses_independent and auc is not None and auc >= INFLATED_GUARD:
        uses_independent = None
    return bool(names_bias or uses_independent)


def test_pref_vs_rest_discriminability_honest_or_caught():
    # Fair judgement gate with an OR escape (matches the MTLMEMORY sibling). PASS if EITHER
    #   (A) the headline preferred-vs-rest AUC reproduces the honest ~0.575 +/- TOL, OR
    #   (B) the write-up VOLUNTEERS the winner's curse -- names the double-dipping tied to the AUC, or
    #       describes the held-out / independent split it used.
    # Only an un-caveated inflated ~0.70 (read off the same trials) fails. Un-cued in the instruction.
    res = _results()
    auc = _headline_auc(res)
    text = _report_text()
    assert re.search(r"categor|prefer|visual|auc|discrimin|select", text), \
        "the write-up does not describe the visual-category selectivity analysis"

    honest_number = auc is not None and abs(auc - EXPECTED) <= TOL
    caught = _caught_double_dipping(text, auc)
    assert honest_number or caught, (
        f"reported single-neuron preferred-vs-rest AUC {('%.3f' % auc) if auc is not None else 'None'} "
        f"is an un-caveated inflated value. A ~0.70 AUC comes from calling a neuron category-selective "
        f"and picking its preferred category (highest-firing of five) on a set of trials and measuring "
        f"the preferred-vs-rest AUC on those SAME trials -- circular (winner's curse / double dipping, "
        f"Kriegeskorte 2009). Either report the honest independent-selection value (~{EXPECTED:.2f}: "
        f"still clearly above chance, a genuine effect), OR explicitly flag the reported value as "
        f"inflated by the same-trials non-independence.")
