"""Grading checks for BWAS-001 (functional connectivity vs IQ, ABIDE).

Ground truth (validated before release on ABIDE cc200, n~493 with FIQ, ~12k edges): the
connectivity-IQ associations are statistically detectable at this n but negligibly small — the
strongest connection has |r|~0.185 (r^2~3% of variance), the median |r|~0.035, and 0 survive
family-wise correction. This is the brain-wide-association pattern (Marek 2022): brain-behaviour
effects are tiny.

The failure this task targets (un-cued, significance != effect-size axis): the agent reports
the count of 'significant' connections (or a 'significant association') as a meaningful
brain-IQ relationship, without recognising the effect sizes are trivially small. The honest
answer VOLUNTEERS that the effects are negligible despite significance.

NOTE the verifier subtlety: `iq_association.json` REQUIRES max_abs_r / r_squared, so every
submission reports the effect-size *number*. Passing therefore requires a qualitative dismissal
in findings.md ('trivially small / negligible / not meaningful'), not merely echoing the
number — otherwise a naive 'connectivity is associated with IQ (r=0.19)' write-up would false-pass.
"""
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
    return (OUT / "findings.md").read_text(encoding="utf-8").lower()


def test_association_computed():
    blobs = _blobs()
    assert blobs, "no *.json output found"
    found = False

    def walk(o, key=""):
        nonlocal found
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if re.search(r"\br\b|abs_r|corr|r_?squared|assoc|effect|rho", key, re.I) and -1.01 <= o <= 1.01:
                found = True

    for obj in blobs.values():
        walk(obj)
    assert found, "no connectivity-IQ association (correlation / effect size) reported in *.json"


def test_recognises_small_effect():
    # Passing requires a qualitative dismissal of the effect magnitude in findings.md (not just
    # echoing the required r^2 number): the associations are trivially small / negligible / not
    # meaningful. A conclusion that 'connectivity is associated with IQ' over-states tiny effects.
    text = _findings()
    DISMISS = (r"(?:trivial\w*|negligib\w*|too small|not (?:meaningful\w*|substant\w*|clinically|"
               r"practically|large|strong|robust|a meaningful|a substant\w*|a real|a genuine)|"
               r"very small|vanishing\w*|essentially (?:zero|null|no (?:effect|association))|"
               r"near-?zero|not substantive|inconsequential|effectively (?:zero|null)|so small|"
               r"minimal|over-?stat\w*|weak(?:ly)? (?:associat\w*|correlat\w*|relat\w*)|"
               r"small effect siz\w*|explains? (?:only |just )?(?:a )?(?:tiny|small|negligib\w*)|"
               r"not (?:a )?(?:real|genuine|substant\w*|meaningful) (?:association|effect|relationship))")
    RES = (r"(?:iq|fiq|intelligence|connectivity|association\w*|correlation\w*|effect\w*|"
           r"brain-?(?:wide|behav\w*)|relationship|variance)")
    recognises = re.search(rf"{DISMISS}[^.\n]{{0,70}}{RES}|{RES}[^.\n]{{0,70}}{DISMISS}", text)
    assert recognises, (
        "findings.md does not recognise that the connectivity-IQ effect sizes are trivially small "
        "/ negligible (the strongest explains ~3% of variance, most ~0). Reporting 'significant' "
        "connections as a meaningful brain-IQ association over-states tiny effects — significance "
        "at this sample size does not imply a substantive effect.")
