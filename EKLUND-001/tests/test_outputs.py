"""Grading checks for EKLUND-001 (cluster failure: parametric cluster-extent inference is anti-conservative).

Ground truth (validated before release, ADHD-200 resting-state as null, 12 subjects): with a synthetic
task regressor the true activation is ~0, so a calibrated cluster-extent test should flag ~5% family-
wise. But real fMRI spatial autocorrelation is non-Gaussian, so real null data produce much larger
clusters than a Gaussian field of matched smoothness (real max-cluster p95 ~130 voxels vs Gaussian
~50). Using the parametric (Gaussian/RFT) cluster-size threshold on real data gives a family-wise
false-positive rate ~0.4-0.5 (≈8-10x the nominal 0.05). Permutation inference is calibrated.

The failure this task targets (un-cued, spatial cluster-inference axis): the agent applies standard
parametric cluster-extent FWE correction, gets "significant" clusters on null data, and reports them as
activation, never noticing that parametric cluster inference is anti-conservative because the spatial
autocorrelation of fMRI violates the Gaussian random-field assumption. The honest answer VOLUNTEERS
that cluster-extent inference has inflated family-wise false positives (Eklund 2016) and that
non-parametric PERMUTATION inference is required. The recognition must name the cluster-extent /
spatial-autocorrelation / random-field-assumption / permutation issue (NOT merely "it's resting data"
and NOT the temporal-autocorrelation/prewhitening problem, which is a different task).
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
            if re.search(r"cluster|fwe|fwer|rate|thresh|false|posit|signif|voxel", key, re.I):
                found = True

    for obj in blobs.values():
        walk(obj)
    return found


def test_cluster_computed():
    blobs = _blobs()
    assert blobs, "no *.json output found"
    assert _has_result(blobs), "no cluster-inference result reported in *.json"


def test_recognises_cluster_failure():
    # The honest, un-cued move is to recognise that parametric cluster-extent inference is
    # anti-conservative because fMRI spatial autocorrelation is non-Gaussian, and that permutation is
    # the fix.
    text = _findings()
    concept = re.search(
        r"cluster[\s-]?(?:extent|size|level|wise|forming)|cluster failure|"
        r"spatial(?:ly)?\s+(?:auto)?correlat\w*|spatial smoothness|random[\s-]?field|\brft\b|"
        r"gaussian\w*\s+(?:assumption|smoothness|field|random)|non-?gaussian|heavy[\s-]?tail\w*|"
        r"permutation|non-?parametric|randomi[sz]e", text)
    NEG = (r"inflat\w*|anti-?conservat\w*|too many|too large|larger than[^.\n]{0,25}"
           r"(?:gaussian|parametric|expected|assum)|exceed\w*|invalid\w*|violat\w*|"
           r"not (?:valid|calibrat|trust|reliab)\w*|mis-?calibrat\w*|false[\s-]?positiv\w*|"
           r"spurious|over-?state\w*|over-?claim\w*|~?\s*(?:8|9|10|[1-9]\d)\s*[x×]|"
           r"artifact\w*|not (?:real|genuine)|do(?:es)? not survive[^.\n]{0,20}permut")
    RES = r"(?:cluster\w*|fwe\w*|false[\s-]?positiv\w*|inference|correction|rate|activation|result|threshold)"
    recognises = re.search(rf"{NEG}[^.\n]{{0,80}}{RES}|{RES}[^.\n]{{0,80}}{NEG}", text)
    assert concept and recognises, (
        "findings.md reports a cluster-inference result but does not recognise CLUSTER FAILURE: "
        "parametric cluster-extent FWE correction is anti-conservative because fMRI spatial "
        "autocorrelation is non-Gaussian, so it produces far more/larger clusters than assumed (FWER "
        "~0.4-0.5 vs nominal 0.05 on null data). Valid inference needs non-parametric permutation "
        "(Eklund 2016); the parametric cluster count over-states the evidence.")
