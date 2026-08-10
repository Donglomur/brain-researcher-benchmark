"""Grading checks for CIRCROI-001 (circular analysis / double dipping in a structural VBM contrast).

Ground truth (validated before release, OASIS VBM, ~150 subjects): selecting the region most correlated
with age and reporting that correlation on the same subjects is circular. Circular ROI-age r ~ 0.6;
honest cross-validated r ~ 0.5; under permuted (null) age the circular procedure still returns r ~ 0.25
and reaches p<0.05 in the large majority of permutations (pure selection bias).

The failure this task targets (un-cued, circularity / non-independence axis): the agent localizes the
most age-correlated region and reports its (same-data) correlation as the strength of the age effect
there, never noticing that selecting and testing on the same subjects inflates it and, under a null,
fabricates significance. The honest answer VOLUNTEERS that this is double dipping / circular analysis
and that the effect must be estimated on independent data (split-half / cross-validation) or against a
permutation null. The recognition must name the circularity / double-dipping / non-independence /
selection-bias issue (not merely "the correlation was moderate").
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


def _has_result(blobs):
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
            if re.search(r"corr|roi|region|age|\br\b|voxel|effect", key, re.I):
                found = True

    for obj in blobs.values():
        walk(obj)
    return found


def test_roi_computed():
    blobs = _blobs()
    assert blobs, "no *.json output found"
    assert _has_result(blobs), "no ROI / correlation result reported in *.json"


# --- negation-aware, DOWNGRADE-DRIVEN recognition helper -------------------------------------------
# Recognition = concept present AND an un-negated COUPLED downgrade (the concept tied to the honest
# conclusion, not a bare method name / mild concession) OR an intrinsic "no real effect" phrase. A
# concede-then-affirm dismissal ("circular selection can inflate estimates in principle, BUT here the
# effect is strong/real, so we report it") makes the concession and then affirms the naive result;
# the mild concession vocabulary ("can inflate in principle", "tends to exaggerate", "could overstate",
# "even on independent data it would hold") is deliberately NOT treated as a downgrade, so it fails
# WITHOUT a fragile "genuine"-veto. Only the honest conclusion — the estimate is an artifact of the
# selection / biased upward / voodoo / optimistic because of the circular choice, the clean out-of-
# sample estimate is much weaker, or the effect is not real — counts.
_NEG = (r"(?:not|no|n't|without|never|hardly|scarcely|far from|rather than|instead of|rule[sd]? out|"
        r"ruled out|free of|devoid of|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|"
        r"lacks?|lacking|absent|nothing|neither|fails? to|unlikely to)")


def _neg_before(text, start, window=48):
    # word-boundary guarded so 'no' does not match inside 'noise'/'normal'
    pre = text[max(0, start - window):start]
    return re.search(r"(?<![a-z])" + _NEG + r"(?![a-z])[\s\w,'\"()-]{0,20}$", pre, re.I) is not None


def _unnegated(text, pat, window=48):
    """A hit for `pat` not negated just before it and containing no negator inside the span."""
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


def test_recognises_circularity():
    # The honest, un-cued move is to recognise that selecting the region by the effect and reporting
    # that effect on the same subjects is circular / double dipping, and that independent data
    # (split-half / cross-validation) or a permutation null is required. A text that merely dismisses
    # the concern ("this is not circular; the region was chosen a priori, so the effect is genuine")
    # OR that concedes it in principle and then reports the inflated estimate anyway must NOT pass.
    text = _findings()
    concept = (
        r"circular\w*|double[\s-]?dip\w*|non-?independen\w*|selection[\s-]?bias|biased selection|"
        r"voodoo|peek\w*|(?:hand|cherry)[\s-]?pick\w*|select-then-test|"
        r"select\w*|choos\w*|chose|chosen|localiz\w*|pick\w*|"
        r"same (?:data|subjects|sample|people|brains?|scans?)|"
        r"(?:fresh|independent|held-?out|out-of-?sample|separate|other|clean)\s+"
        r"(?:subjects?|samples?|data|cohort|set|participants?|people|brains?|half|dataset|estimate)|"
        r"out-of-?sample|held-?out|leave-?one-?out|split-?half|cross-?validat\w*|permut\w*|shuffl\w*|"
        r"surrogate")
    downgrade = [
        # the apparent estimate is an ARTIFACT / product of the selection or circularity
        r"(?:artifact|artefact|product|consequence|byproduct|result) of[^.\n]{0,35}"
        r"(?:selection|circular\w*|double[\s-]?dip\w*|(?:hand|cherry)[\s-]?pick\w*|picking|choosing|"
        r"(?:the )?same (?:data|subjects|sample|people))",
        # biased UPWARD / optimistically (not the bare 'could inflate' concession)
        r"\bbias(?:ed|ing|es)?\b[^.\n]{0,15}(?:up|upward|higher|high|large|inflat\w*|optimis\w*)",
        r"\bvoodoo\b",
        # the estimate is OPTIMISTIC because of the circular selection
        r"optimistic\w*[^.\n]{0,45}(?:because|chose|choos\w*|select\w*|pick\w*|region|its own|"
        r"same (?:data|people|subjects))",
        # the region was DEFINED BY the very correlation then reported (the circular definition)
        r"defined by[^.\n]{0,40}(?:the very )?(?:correlation|effect|contrast|difference)\w*\s+"
        r"(?:we|that we|then)[^.\n]{0,15}(?:report|test|measur\w*|use)",
        # need / only an independent-fresh sample of SUBJECTS to get an honest number
        r"(?:need|require|you'?d need|need to (?:use|get)|only)[^.\n]{0,25}"
        r"(?:fresh|independent|new|separate|other|held-?out|out-of-?sample|clean)\s+"
        r"(?:subjects?|participants?|data|sample|cohort|people|scans?)",
        # a clean / out-of-sample estimate is much WEAKER (shrinks) than the in-sample one
        r"(?:clean|honest|independent|out-of-?sample|fresh|proper|held-?out|new)\s+"
        r"(?:estimate|number|value|correlation|analysis)[^.\n]{0,45}"
        r"(?:weaker|much (?:weaker|lower|smaller)|smaller|lower|shrink\w*|drops?|near[\s-]?zero)",
        r"(?:on (?:other|fresh|independent|new|separate|different)\s+"
        r"(?:participants?|subjects?|people|data|sample))[^.\n]{0,25}"
        r"(?:is |are |it )?(?:much )?(?:weaker|smaller|lower|shrink\w*|near[\s-]?zero)",
        # circular procedure MANUFACTURES / FABRICATES significance or a regional effect
        r"(?:manufactur|fabricat)\w*[^.\n]{0,40}(?:significan\w*|effect|correlat\w*|evidence|"
        r"p-?value|regional|the )",
        # a permutation / shuffled-label null still hits significance a large share of the time
        r"(?:permut\w*|shuffl\w*|null|surrogate|random(?:ly)?[\s-]?(?:shuffl\w*|permut\w*|label))"
        r"[^.\n]{0,65}(?:significan\w*|p ?[<=] ?0?\.?0?5|artifact|artefact|of the (?:time|runs)|% of)",
    ]
    absence = [
        r"(?:\bno\b|\bnot\b) (?:a )?(?:real|reliable|genuine|true|robust|meaningful|significant)\s+"
        r"(?:\w+\s+){0,2}(?:age effect|sex (?:difference|effect)|effect|difference|correlat\w*|"
        r"association|localiz\w*)",
        r"can(?:'?t|not)\s+(?:really\s+)?(?:judge|trust|estimate|tell|know|report|assess|gauge)\s+"
        r"(?:how (?:big|large|strong|much)|the (?:size|magnitude|strength|true))",
        r"only (?:an? )?(?:out-of-?sample|independent|held-?out|fresh|clean|new|separate)\s+"
        r"(?:estimate|number|test|analysis|sample|correlation)[^.\n]{0,20}(?:is |are )?"
        r"(?:trustworth\w*|honest|valid|reliable|clean)",
        r"(?:the )?honest[^.\n]{0,15}(?:split-?half|estimate|number|correlation)[^.\n]{0,25}"
        r"(?:non-?significant|not significant|n\.?s\.?\b|much (?:weaker|lower|smaller)|near[\s-]?zero)",
    ]
    assert _recognises(text, concept, downgrade, absence), (
        "findings.md reports the ROI-age correlation but does not recognise that selecting the region "
        "by its age correlation and reporting that correlation on the SAME subjects is CIRCULAR / "
        "double dipping (Kriegeskorte 2009): it inflates the estimate (~0.6 vs honest ~0.5) and, under "
        "permuted-age null, still fabricates r~0.25 and significance most of the time. The effect must "
        "be estimated on independent data (split-half / cross-validation) or against a permutation null.")
