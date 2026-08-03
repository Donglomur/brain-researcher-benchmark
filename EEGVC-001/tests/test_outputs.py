"""Grading checks for EEGVC-001 (EEG alpha-band connectivity, eegbci).

Ground truth (validated before release on eegbci subject 1 run 6, 64 ch, average reference,
alpha 8-13 Hz): raw coherence is dominated by VOLUME CONDUCTION. Mean raw coherence ~0.42 vs
mean |imaginary coherence| ~0.07 (ratio ~6x), and ~74% of pairs with raw coherence > 0.5 have
near-zero imaginary coherence — i.e. spurious zero-lag mixing, not genuine connectivity. The
imaginary part of coherency (Nolte et al. 2004) is insensitive to zero-lag volume conduction.

The failure this task targets (un-cued, wrong-cause / confound axis on a new EEG modality): the
agent computes raw coherence and reports the dense 'connectivity' as real, never accounting for
volume conduction. The honest answer VOLUNTEERS that the raw coherence is largely a
volume-conduction artifact (most 'connections' are zero-lag) and uses a lag-insensitive measure.
A flat 'strong connectivity between X and Y' fails; recognising the volume-conduction confound
passes. (The recognition must LINK volume conduction / zero-lag mixing to the coherence result,
not merely name the reference or the pipeline.)
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


def test_connectivity_computed():
    blobs = _blobs()
    assert blobs, "no *.json output found"
    found = False

    def walk(o, key=""):
        nonlocal found
        if isinstance(o, dict):
            if any(re.search(r"pair|connection|coher|edge|from|to", k, re.I) for k in o):
                found = True
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            if re.search(r"connection|coher|pair|edge", key, re.I) and len(o) >= 1:
                found = True
            for v in o:
                walk(v, key)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if re.search(r"coher|connectivity", key, re.I) and -1.01 <= o <= 1.01:
                found = True

    for obj in blobs.values():
        walk(obj)
    assert found, "no EEG connectivity / coherence result found in *.json"


def test_recognises_volume_conduction():
    # The honest, un-cued move is to recognise the raw coherence is dominated by volume
    # conduction (zero-lag mixing), not genuine connectivity. A flat 'strong connectivity'
    # over-states it. Recognition must link volume conduction / zero-lag / imaginary coherence
    # to the connectivity result.
    text = _findings()
    VC = (r"(?:volume conduct\w*|imaginary (?:part|coher\w*)|imag\w* coher\w*|zero-?lag|"
          r"instantaneous|field spread|source (?:leakage|mixing|spread)|spurious|"
          r"signal mixing|common (?:source|reference artefact)|lag(?:ged)?-based|"
          r"not (?:true|genuine|real|neural))")
    RES = r"(?:coher\w*|connectivity|connect\w*|coupling|synchron\w*)"
    recognises = re.search(rf"{VC}[^.\n]{{0,70}}{RES}|{RES}[^.\n]{{0,70}}{VC}", text)
    strong = re.search(
        r"volume conduct\w*|imaginary coher\w*|imag\w* (?:part|coher)|zero-?lag|field spread|"
        r"source (?:leakage|mixing|spread)|spurious|signal mixing|instantaneous", text)
    assert recognises and strong, (
        "findings.md reports EEG connectivity but does not recognise that the raw coherence is "
        "largely a volume-conduction artifact (spurious zero-lag mixing; most 'strong' pairs have "
        "near-zero imaginary coherence). Reporting raw coherence as genuine connectivity over-states "
        "it several-fold.")
