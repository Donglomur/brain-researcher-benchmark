"""Proof-of-work grader for RATPLACE-001 (CA1 place-cell Skaggs spatial information).

Ground truth (validated before release on DANDI 001754, sub-Rat1 ses-19980425, both Baseline
rectangular-track (BL) epochs, running > ~5 px/s, 4x5 = 20-bin occupancy grid, putative pyramidal
CA1 units, 300 circular shifts):

  n CA1 units                 = 36
  RAW   mean Skaggs info      = 1.12 bits/spike   # looks like textbook place coding
  SHUFFLE-null mean           = 1.03 bits/spike   # == the estimator's finite-sample/occupancy bias
  BIAS-CORRECTED mean         = 0.09 bits/spike    # far below raw

The Skaggs spatial-information estimator is positively biased at finite sample size: with a limited
number of spikes over a binned arena, even a spatially RANDOM cell yields a positive apparent
information, because under-sampled bins make the rate map look tuned by chance. The un-cued lever is
therefore the ESTIMATOR BIAS: the raw ~1.1 bits/spike is dominated by that bias, and a shuffle /
circular-shift correction (what every place-cell paper does) brings the value far down (~0.09 at this
binning). The graded scientific conclusion is this estimator-bias lesson -- raw over-estimates, a
bias correction is required, and the corrected value is much lower than raw -- NOT a biological claim
that CA1 lacks place coding (that would over-reach: a finer grid / 1-D linearisation recovers
spatially tuned cells, as expected for CA1; the 20-bin corrected value speaks to the estimator and
this binning's power, not to the biology).

The failure mode this task targets (un-cued): the agent computes the raw Skaggs info, gets ~1.1
bits/spike, and reports it as real place coding -- never establishing that the value is dominated by
estimator bias.

PROOF OF WORK (fabrication-proof, lever kept un-cued):
  * Pillar 1 -- the submitted per-unit table (NEUTRAL: the pinned per-unit RAW Skaggs information,
    which BOTH a raw-only and a bias-corrected analysis produce) must match the held-out reference
    (tests/reference.npz): cover the real unit ids, be non-constant, track the reference per-unit raw
    (cross-unit r >= 0.95, per-unit tol). Impossible without the real occupancy + spikes.
  * Pillar 2 -- recompute the raw population mean FROM the submitted rows and cross-check it against
    the reference (1.12) and the reported JSON.
  * Pillar 3 -- the scientific JUDGEMENT, graded un-cued as an OR-escape: PASS if the write-up
    VOLUNTEERS the estimator bias -- EITHER by reporting a bias-corrected value far below the raw
    mean, OR in prose (raw over-estimates / inflated by finite-sample-occupancy bias / a shuffle
    correction is needed) tied to the spatial-information result. Reporting only the raw ~1.1 as real
    coding fails. A definitive BIOLOGICAL-ABSENCE over-claim (CA1 carries no place coding) with no
    estimator/binning scoping also fails -- the graded lesson is the estimator bias, not a biological
    null.
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

RAW_TOL = 0.06        # per-unit raw Skaggs abs match
CORR_MIN = 0.95       # cross-unit corr(submitted raw, reference raw) -- fabrication teeth
COVER = 0.90
RAWMEAN_TOL = 0.10    # raw population mean recomputed-from-rows vs reference and vs reported
CORRECTED_MAX = 0.5   # a genuine bias-corrected mean sits well below the raw ~1.1
BIAS_MARGIN = 0.4     # corrected must be at least this far below the raw mean


def _load_json(name):
    p = OUT / name
    assert p.exists(), f"missing required output {name}"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"{name} is not valid JSON: {e}")


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "spatial_information.csv"
    assert p.exists(), "missing required output spatial_information.csv"
    return pw.load_submitted(
        p,
        id_cols=("unitindex", "unit", "unitid", "index", "cellid", "cell", "id"),
        raw_cols=("spatialinformationbitsperspike", "spatialinformation", "skaggs", "bitsperspike",
                  "rawbitsperspike", "information", "infobitsperspike", "raw"))


def _blob():
    s = ""
    for name in ("findings.md", "results.json", "run_metadata.json", "spatial_information.csv"):
        p = OUT / name
        if p.exists():
            s += "\n" + p.read_text(encoding="utf-8")
    return s.lower()


def _prose():
    """The write-up only (NOT the data CSV -- its column headers would leak method vocabulary)."""
    s = ""
    for name in ("findings.md", "results.json", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            s += "\n" + p.read_text(encoding="utf-8")
    return s.lower()


# ------------------------------------------------------------------ well-formedness
def test_spatial_information_computed():
    sub, raw = _submitted()
    assert len(raw) >= 20, f"expected ~36 CA1 units in spatial_information.csv, got {len(raw)}"
    mean = sum(raw) / len(raw)
    assert 0.2 < mean < 4.0, f"per-unit spatial information out of plausible range (mean {mean:.3f})"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_units_and_values():
    ref = _reference()
    sub, _ = _submitted()
    pw.check_units_and_values(sub, ref, raw_tol=RAW_TOL, cover=COVER, corr_min=CORR_MIN)


# ------------------------------------------------------------------ pillar 2
def test_recompute_raw_mean():
    ref = _reference()
    sub, _ = _submitted()
    matched = [i for i in sub if i in set(ref["ids"])]
    raw_mean = pw.recompute_raw_mean(sub, matched)
    ref_raw = float(ref["stats"]["raw_mean"])
    assert raw_mean == raw_mean, "cannot recompute the raw population mean from the submitted rows"
    assert abs(raw_mean - ref_raw) <= RAWMEAN_TOL, (
        f"raw Skaggs population mean recomputed from the rows ({raw_mean:.3f}) does not match the "
        f"reference ({ref_raw:.3f}, tol {RAWMEAN_TOL}). The per-unit rows are not the real analysis.")
    # if a raw / uncorrected mean is reported in JSON, it must agree with the rows.
    res = _load_json("results.json")
    reported_raw = pw.find_number(res, [r"raw.*mean", r"raw.*info", r"uncorrected"],
                                  exclude=[r"correct", r"shuffle", r"null", r"nsig", r"^n"])
    if reported_raw is not None:
        assert abs(reported_raw - raw_mean) <= max(RAWMEAN_TOL, 0.05), (
            f"reported raw mean ({reported_raw:.3f}) is inconsistent with the submitted rows "
            f"({raw_mean:.3f}).")


# ------------------------------------------------------------------ pillar 3 (judgement, un-cued)
_BIAS_PROSE = (
    r"(?:bias\w*|inflat\w*|over[- ]?estimat\w*|overstate\w*|artefact\w*|artifact\w*|spurious|"
    r"finite[- ]?sampl\w*|small[- ]?sampl\w*|occupanc\w*|under[- ]?sampl\w*|chance level|"
    r"positively biased|not corrected|before correction|shuffle|circular\w*|permut\w*|surrogate)")
_INFO = (r"(?:spatial info\w*|skaggs|bits?/?\s*spike|information|place (?:cod\w*|cell|field)|"
         r"spatial (?:cod\w*|tuning)|raw)")
_NEG = (r"\b(?:not|no|never|isn'?t|aren'?t|wasn'?t|without|hardly|doesn'?t|don'?t|do not|does not)\b"
        r"[\s\-,]*(?:a|an|any|the|really|simply|just|merely|evidence|sign|of)*[\s\-,]*$")


def _reported_corrected(res):
    """A value the submission labels as bias-corrected / debiased / adjusted."""
    return pw.find_number(res, [r"correct", r"debias", r"adjusted", r"bias.*subtract"],
                          exclude=[r"raw", r"uncorrected", r"nsig", r"null.*mean"])


def _bias_recognised_in_prose(text):
    """A bias term, non-negated, in the same sentence as a spatial-information/result token."""
    for m in re.finditer(_BIAS_PROSE, text):
        if re.search(_NEG, text[max(0, m.start() - 30):m.start()]):
            continue
        lo = max(text.rfind(".", 0, m.start()), text.rfind("\n", 0, m.start())) + 1
        ends = [x for x in (text.find(".", m.end()), text.find("\n", m.end())) if x != -1]
        hi = min(ends) if ends else len(text)
        seg = text[lo:hi]
        if re.search(_INFO, seg):
            return True
    return False


def test_estimator_bias_volunteered():
    # Un-cued OR-escape. PASS if the write-up VOLUNTEERS the Skaggs estimator bias: EITHER a reported
    # bias-corrected value far below the raw mean, OR prose that ties the bias/over-estimation to the
    # spatial-information result. Reporting only the raw ~1.1 as real place coding fails.
    res = _load_json("results.json")
    ref = _reference()
    ref_raw = float(ref["stats"]["raw_mean"])
    text = _prose()
    assert re.search(r"spatial info|skaggs|bits?/?\s*spike|place (?:cod|cell|field)", text), \
        "the write-up does not describe the spatial-information analysis"

    corrected = _reported_corrected(res)
    corrected_ok = (corrected is not None and corrected <= CORRECTED_MAX
                    and corrected <= ref_raw - BIAS_MARGIN)
    prose_ok = _bias_recognised_in_prose(text)
    assert corrected_ok or prose_ok, (
        "the submission reports the raw Skaggs information as real spatial coding without recognising "
        "the estimator bias. The raw ~1.1 bits/spike is dominated by the Skaggs finite-sample / "
        "occupancy bias; a shuffle / circular-shift correction (what every place-cell paper does) "
        "brings it far down (~0.1 at this 20-bin binning). Either report a bias-corrected value far "
        "below the raw mean, or state that the raw value over-estimates / is inflated by the "
        "estimator's finite-sample bias.")


def test_does_not_overclaim_biological_absence():
    # R2 rework: the graded conclusion is the ESTIMATOR bias, NOT a biological 'no place coding' null.
    # A definitive biological-absence claim (CA1 carries no spatial information / no place cells / place
    # coding is absent) OVER-CLAIMS: a finer grid / linearisation recovers spatially tuned cells. Only
    # fire when such a claim is made WITHOUT an estimator/binning scoping caveat anywhere in the text
    # (so a scoped statement -- 'at this 20-bin grid, after correction, the value is ~0' with an
    # explicit 'this does not mean CA1 lacks place fields' -- passes).
    text = _prose()
    absence = re.search(
        r"(?:ca1|these cells|the (?:cells|units|population|neurons)|hippocamp\w*)[^.\n]{0,40}"
        r"(?:carr\w*|have|contain\w*|show\w*|encod\w*)?[^.\n]{0,20}"
        r"(?:no|not|zero|lack\w*|absen\w*|without)[^.\n]{0,25}"
        r"(?:spatial (?:info\w*|cod\w*|tuning)|place (?:cod\w*|cell|field))"
        r"|(?:no|not|zero|lack\w*|absen\w*)[^.\n]{0,20}place (?:cod\w*|cell|field)"
        r"|(?:are|were) not place cells",
        text)
    if not absence:
        return
    # a scoping / estimator caveat that keeps the claim about the estimator or this binning, not biology
    scoped = re.search(
        r"at this (?:binning|grid|resolution)|this (?:coarse |20[- ]?bin |binning)|"
        r"estimator|finer (?:grid|bin)|lineari[sz]|does not (?:mean|imply|establish|prove)|"
        r"not (?:that |a )?(?:biological|absence of|evidence (?:that|of) ca1|proof)|"
        r"not that ca1|does not (?:rule out|exclude)|may (?:still )?(?:be|have) place|"
        r"binning[- ]?depend|under[- ]?power",
        text)
    assert scoped, (
        "the write-up over-claims a BIOLOGICAL absence of place coding in CA1. The corrected value at "
        "this 20-bin binning speaks to the Skaggs estimator bias and this binning's power, not to the "
        "biology: a finer grid / 1-D linearisation recovers spatially tuned cells in CA1. Frame the "
        "conclusion as the estimator bias (raw over-estimates; the corrected value is much lower), and "
        "do not assert that CA1 lacks place coding.")
