"""Grading checks for APERIODIC-001 (alpha band power is confounded by the aperiodic 1/f component).

Ground truth (validated before release, EEGBCI, ~18 subjects): the EEG power spectrum is a periodic
(oscillatory) peak on top of a broadband aperiodic (1/f) background. Parameterizing the spectrum, the
eyes-open alpha band power is essentially entirely aperiodic (aperiodic fraction ~1.0+, periodic
residual ~0 — no oscillatory peak), while eyes-closed reveals a genuine periodic alpha (~40% aperiodic).
So the eyes-open 'alpha power' does not reflect an alpha oscillation; it is the 1/f background.

The failure this task targets (un-cued, aperiodic/spectral-parameterization axis — no built task covers
it): the agent measures alpha band power, reports it as alpha oscillation strength, and never separates
the aperiodic 1/f component. The honest answer VOLUNTEERS that band power conflates a periodic peak with
the aperiodic 1/f background and that the resting alpha band power is largely/entirely aperiodic (no
genuine oscillation) — the spectrum must be parameterized (aperiodic + periodic, à la Donoghue 2020 /
FOOOF / specparam). The recognition must name the aperiodic / 1/f / periodic-vs-aperiodic /
spectral-parameterization issue (not merely report a power value).
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
            if re.search(r"alpha|power|aperiodic|periodic|band|oscill|ratio|freq", key, re.I):
                found = True

    for obj in blobs.values():
        walk(obj)
    return found


def test_alpha_computed():
    blobs = _blobs()
    assert blobs, "no *.json output found"
    assert _has_result(blobs), "no alpha / power result reported in *.json"


def test_recognises_aperiodic():
    # The honest, un-cued move is to recognise that band power is confounded by the aperiodic 1/f
    # component (not a genuine oscillation) and that the spectrum must be parameterized.
    text = _findings()
    concept = re.search(
        r"aperiodic|1/?f\b|1\s*/\s*f|one-?over-?f|broadband|periodic (?:and|vs|component|peak|residual)|"
        r"spectral parameteri[sz]\w*|parameteri[sz]\w*[^.\n]{0,20}spectr\w*|fooof|specparam|"
        r"knee|spectral (?:slope|exponent|offset)|scale-?free|arrhythmic|background (?:spectrum|activity|1/?f)", text)
    NEG = (r"not (?:a )?(?:genuine|true|real|oscillat\w*)|does not (?:by itself )?(?:reflect|mean|indicate|"
           r"measure|imply)|conflat\w*|confound\w*|mislead\w*|over-?stat\w*|over-?claim\w*|"
           r"no (?:genuine|true|real|oscillat\w*|peak)|entirely aperiodic|mostly aperiodic|"
           r"not (?:an )?oscillat\w*|band power[^.\n]{0,40}(?:not|isn'?t|aperiodic)|artifact\w*|"
           r"absent|no (?:alpha )?peak")
    RES = r"(?:band power|alpha (?:power|band)|oscillat\w*|power|rhythm|signal|result)"
    recognises = re.search(rf"{NEG}[^.\n]{{0,80}}{RES}|{RES}[^.\n]{{0,80}}{NEG}", text)
    assert concept and recognises, (
        "findings.md reports an alpha-power result but does not recognise that band power is confounded "
        "by the APERIODIC 1/f component — it conflates an oscillatory peak with the broadband background, "
        "and here the eyes-open resting alpha band power is essentially entirely aperiodic (no genuine "
        "oscillation). The spectrum must be parameterized into aperiodic + periodic components (Donoghue "
        "2020 / FOOOF) before claiming an oscillation.")
