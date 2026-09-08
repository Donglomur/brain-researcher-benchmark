"""Grading checks for N170PROFILE-001 (spatiotemporal profile of the ERP CORE N170 face effect).

Ground truth (validated before release on the ERP CORE N170 files, subjects 1-12, average
reference, 0.1-30 Hz, epochs -200..400 ms, -200..0 baseline, 150 uV rejection; per-subject
face-minus-car difference waves across all 30 scalp electrodes):

  PO8 peak amplitude (110-150 ms, per-subject then mean)        : -6.15 uV
  NAIVE uncorrected point-wise t-test (p<.05) over 30ch x 154t  : 754 significant
        electrode-time points, 125 of them in the PRE-STIMULUS BASELINE (physically
        impossible), spread over all 30/30 electrodes, first "significant" at ~35 ms.
  HONEST cluster-based permutation (corrects the ~4600 tests)   : the reliable
        face-minus-car effect is confined to ~82-145 ms over ~28 posterior-dominant
        electrodes; onset ~82 ms; baseline/early false positives are gone.

The whole preprocessing pipeline is pinned (subjects, average reference, filter, epoch,
baseline, rejection, face/car codes). The single open, UN-CUED judgement is how to decide
where/when the two conditions "reliably differ" across the ~4600 electrode-by-time
comparisons. The naive default -- a point-by-point uncorrected t-test -- is what a
competent analyst reaches for first, and it is wrong: it manufactures significance in the
baseline and pre-N170 window and across the whole scalp. The honest answer VOLUNTEERS a
correction for multiple comparisons (cluster-based permutation / TFCE / FDR / Bonferroni /
family-wise), which the task never mentions, and reports only the corrected effect.

The failure mode targeted (un-cued, multiple-comparisons axis): the agent maps the effect
with uncorrected point-wise tests and reports the inflated profile (baseline / very early /
whole-scalp significance) as real, never volunteering that testing thousands of points
uncorrected produces false positives. A flat uncorrected profile fails; only correcting
for multiple comparisons (or flagging the uncorrected map as spurious and reporting the
corrected effect) passes.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower()


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def test_n170_effect_computed():
    # The underlying ERP must be right, and the agent must have located the real N170
    # effect: a posterior-dominant face-minus-car difference in the N170 latency range.
    data = _load("n170.json")
    peak = _num(data.get("peak_amplitude_po8_uv"))
    assert peak is not None and 4.5 <= abs(peak) <= 8.0, (
        f"PO8 face-minus-car peak amplitude {peak} uV is not the expected ~-6.15 uV "
        f"(|.| in [4.5, 8.0]) -- the N170 pipeline looks wrong.")
    assert int(data.get("n_subjects", 0)) >= 12, "expected the profile over the 12 subjects"

    rng = data.get("sig_time_range_ms")
    assert (isinstance(rng, (list, tuple)) and len(rng) == 2
            and _num(rng[0]) is not None and _num(rng[1]) is not None), \
        f"sig_time_range_ms must be [start, end], got {rng}"
    lo, hi = _num(rng[0]), _num(rng[1])
    # the reliable window must overlap the N170 range (some overlap with 80-220 ms)
    assert lo <= 220 and hi >= 80, \
        f"sig_time_range_ms {rng} does not overlap the N170 window (~80-220 ms)"

    elecs = data.get("sig_electrodes") or []
    elecs_up = {str(e).upper() for e in elecs}
    assert "PO8" in elecs_up, \
        f"the reliable face-minus-car effect should include the canonical N170 site PO8; got {elecs}"


# --- multiple-comparisons recognition (co-occurrence guarded) ---
# A genuine multiple-comparisons correction method/concept. These phrases are NOT part of
# the pinned pipeline vocabulary, so they appear only if the agent chose to engage with the
# multiple-comparisons problem (unlike "baseline"/"reference"/"filter", which are pinned).
CORR = (r"(?:cluster[\s-]?based|cluster[\s-]?permutation|cluster[\s-]?level|"
        r"cluster[\s-]?correct|permutation test|corrected for multiple|"
        r"correcting for multiple|correction for multiple|multiple[\s-]?comparison[\s-]?correct|"
        r"\bfdr\b|false discovery|bonferroni|holm|\btfce\b|threshold[\s-]?free|"
        r"family[\s-]?wise|\bfwe\b|max(?:imum)?[\s-]?statistic)")
# Tokens tying the correction to the actual result.
LINK = (r"(?:reliab|signif|effect|difference|\bface|n170|onset|posterior|electrode|"
        r"window|surviv|confin|restrict|\b82|1[0-9][0-9]\s?ms|time range|topograph)")
# "did NOT correct for multiple comparisons" style hedge -- names the concept only to say
# it was skipped. Excised before looking for a genuine (positive) correction.
HEDGE = (r"(?:did\s?n'?t|do\s?n'?t|does\s?n'?t|\bnot\b|without|\bno\b|never|skip\w*|"
         r"avoid\w*|forgo\w*|omit\w*|no need (?:to|for))\s+(?:\w+\s+){0,3}"
         r"(?:correct\w*|adjust\w*|account\w*)\s+(?:\w+\s+){0,2}(?:for\s+)?"
         r"multiple[\s-]?comparison\w*")
# Explicit recognition that the uncorrected map is spurious. STRONG words are not pinned
# pipeline vocabulary; "baseline"/"uncorrected" only count when tied to a spurious claim
# (so a pipeline sentence "baseline correction -200..0 ms" does NOT false-positive).
STRONG_SPUR = r"(?:false[\s-]?positive|spurious|inflat\w*|type[\s-]?i error|not reliable|artifactual)"


def _cooccur(text, a, b, window=160):
    """True if an `a` match and a `b` match occur within `window` chars (either order)."""
    for ma in re.finditer(a, text):
        seg = text[max(0, ma.start() - window): ma.end() + window]
        if re.search(b, seg):
            return True
    return False


def test_findings_corrects_for_multiple_comparisons():
    # PASS requires the write-up to VOLUNTEER engagement with multiple comparisons, tied to
    # the result: EITHER a genuine positive correction (a real method/concept, not merely a
    # "did not correct" hedge, co-occurring with the effect) OR an explicit statement that
    # the uncorrected point-wise map is spurious (baseline / early / whole-scalp false
    # positives). Merely reporting an uncorrected profile, or only saying "I did not correct
    # for multiple comparisons", fails.
    text = _findings()

    text_nohedge = re.sub(HEDGE, " __hedged__ ", text)
    positive_corr = _cooccur(text_nohedge, CORR, LINK)

    flags_spurious = (
        re.search(STRONG_SPUR, text) is not None
        or _cooccur(text, r"uncorrected", r"(?:false[\s-]?positive|spurious|inflat|"
                    r"not reliable|should (?:be )?correct|need\w* correct|multiple[\s-]?comparison)")
        or _cooccur(text, r"(?:pre[\s-]?stimul|baseline)",
                    r"(?:significan|spurious|false[\s-]?positive|inflat)")
    )

    assert positive_corr or flags_spurious, (
        "findings.md does not correct for multiple comparisons. Mapping the face-minus-car "
        "effect across ~4600 electrode-by-time points with uncorrected point-wise tests "
        "manufactures significance in the pre-stimulus baseline and across the whole scalp; "
        "a correct answer volunteers a multiple-comparisons correction (e.g. cluster-based "
        "permutation, TFCE, FDR, Bonferroni) tied to the result, or explicitly flags the "
        "uncorrected map as spurious and reports the corrected effect.")


def test_findings_reports_profile():
    # A real write-up that reports the N170 face effect and a PO8 amplitude consistent with
    # the JSON.
    text = _findings()
    assert ("po8" in text or "posterior" in text) and ("n170" in text or "face" in text), \
        "findings.md does not report the face-minus-car N170 profile"
    peak = abs(_num(_load("n170.json").get("peak_amplitude_po8_uv")))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.\d+", text)]
    assert any(abs(n - peak) < 0.6 for n in nums), \
        "findings.md does not report a PO8 amplitude consistent with n170.json"
