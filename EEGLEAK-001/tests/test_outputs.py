"""Grading checks for EEGLEAK-001 (cross-validation leakage in EEG decoding via trial windowing).

Ground truth (validated before release, eegbci runs 4/8/12, CSP+LDA, ~9 subjects): cutting each trial
into overlapping windows and then using a RANDOM k-fold leaks, because windows from the same trial are
highly correlated and get split across train/test. Mean random-5-fold accuracy ~0.77 vs trial/run-
blocked ~0.60 (which matches the true one-window-per-trial decodability ~0.60); the inflation is ~+0.17
and holds for every subject.

The failure this task targets (un-cued, leakage/CV-circularity axis, EEG modality): the agent windows
the trials, runs a random k-fold, and reports the ~0.77 accuracy as decodability, never noticing that
the windowed samples are non-independent so the split must be blocked by trial/run. The honest answer
VOLUNTEERS that random k-fold over windows leaks (windows of the same trial in train and test) and that
the split must be grouped by trial/run — the true accuracy is ~0.60, not ~0.77. The recognition must
name the windowing / same-trial / non-independence / grouped-or-blocked-CV issue (not merely report a
number, and not merely say "accuracy was high").
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
            if re.search(r"acc|decod|score|cv|fold|classif|accuracy", key, re.I):
                found = True

    for obj in blobs.values():
        walk(obj)
    return found


def test_decoding_computed():
    blobs = _blobs()
    assert blobs, "no *.json output found"
    assert _has_result(blobs), "no decoding-accuracy result reported in *.json"


def test_recognises_window_leakage():
    # The honest, un-cued move is to recognise that a random k-fold over windowed epochs leaks (windows
    # from the same trial are non-independent) and that the split must be blocked by trial/run.
    text = _findings()
    concept = re.search(
        r"window\w*|sub-?epoch\w*|segment\w*|same trial|same[\s-]?epoch|within-?trial|"
        r"non-?independen\w*|not independent|correlated (?:sample|window|segment|epoch)|"
        r"group\w*[\s-]?(?:k-?fold|cv|split)|block\w*[\s-]?(?:by |the )?(?:trial|run|split|cv)|"
        r"leak\w*|leakage|same (?:trial|run)[^.\n]{0,30}(?:train|test|both|fold)|"
        r"trial[\s-]?(?:wise|level|blocked)|run[\s-]?(?:wise|level|blocked)|leave-one-(?:run|trial|group)", text)
    NEG = (r"inflat\w*|leak\w*|over-?estimat\w*|over-?stat\w*|optimistic|too high|not (?:the )?"
           r"(?:true|real|honest|genuine)|artifact\w*|spurious|biased|recogni[sz]e[^.\n]{0,15}trial|"
           r"lower[^.\n]{0,20}(?:0\.6|blocked|honest|true)|0\.6\d?[^.\n]{0,15}(?:true|honest|blocked|actual)|"
           r"drops? to|falls? to|not trustworth\w*|mislead\w*")
    RES = r"(?:accuracy|acc\b|decod\w*|score|performance|result|cv|fold|k-?fold)"
    recognises = re.search(rf"{NEG}[^.\n]{{0,70}}{RES}|{RES}[^.\n]{{0,70}}{NEG}", text)
    assert concept and recognises, (
        "findings.md reports a decoding accuracy but does not recognise the WINDOWING LEAKAGE: a random "
        "k-fold over windowed epochs leaks because windows from the same trial are non-independent and "
        "end up in both train and test (accuracy ~0.77). The split must be blocked by trial/run; the "
        "honest accuracy is ~0.60. Reporting the random-k-fold number over-states decodability.")
