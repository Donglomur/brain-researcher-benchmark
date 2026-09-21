"""Proof-of-work grader for HIPPOTHETA-001 (hippocampal theta peak frequency).

Single-value task: the deliverable is one theta peak frequency (Hz). A lone scalar is guessable,
so the grader validates the finest NEUTRAL intermediate the analysis produces -- the power
spectrum the peak is read from -- against a held-out reference (tests/reference.npz, built from
the oracle run, never shipped to the agent), and requires the headline to lie in the honest band
that only a movement-conditioned spectrum reaches.

Ground truth (DANDI 000552, sub-e15-13f1 ses-220117, CA1 LFP 1250 Hz, best-theta-power channel,
Welch 4 s windows, 6-10 Hz band):
  CORRECT  during locomotion            : 9.0 Hz   <-- reported (stable 8.98-9.01 across channels)
  NAIVE    whole recording, no gating    : 7.9 Hz  (REM/immobility slow theta pulls it down)

Theta peak frequency is state-dependent: this ~7 h session is mostly rest/sleep with one ~31 min
maze epoch, so a whole-recording spectrum is dragged toward the slow (REM/immobility) theta at
~7.9 Hz and understates the movement-related theta (~9 Hz). The honest analysis conditions on the
animal's movement state and VOLUNTEERS the state-dependence the task never asks for.

Pillars:
  1. spectrum.csv IS the real movement-conditioned spectrum (5-11 Hz shape tracks the held-out
     reference; ~0.9 across channels vs ~0.14 for the whole-recording spectrum), non-constant
  2. headline theta peak in the honest ~9 Hz band (fails the naive ~7.9), == the peak of the
     submitted spectrum (CSV <-> JSON self-consistency)
  3. discriminating recognition (fail if absent): the state-dependence the honest analysis
     volunteers -- a reported slower non-movement / whole-recording peak (~7.9 Hz) OR prose that
     the theta frequency is state-dependent (running vs rest/REM/immobility)
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

PEAK_BAND = (8.4, 9.6)     # honest movement-related theta ~9 Hz; fails naive whole-recording ~7.9
BAND_CORR_MIN = 0.80
SELF_PEAK_TOL = 0.6


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _results():
    p = OUT / "results.json"
    assert p.exists(), "missing required output results.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _spectrum():
    p = OUT / "spectrum.csv"
    assert p.exists(), (
        "missing required output spectrum.csv -- the power spectrum (frequency, power) the theta "
        "peak is read from. The single peak frequency cannot be validated without the spectrum it "
        "is the argmax of.")
    return pw.load_submitted_spectrum(p)


def _headline(res):
    return pw.find_number(
        res, [r"thetapeak", r"peakfrequency", r"peakfreq", r"thetafrequency", r"peakhz", r"peak"],
        exclude=[r"whole", r"rest", r"rem", r"immobil", r"sleep", r"band", r"channel", r"nperseg",
                 r"window", r"power", r"quiet"])


def test_outputs_present_and_wellformed():
    _reference()
    res = _results()
    hl = _headline(res)
    assert hl is not None, f"results.json exposes no headline theta peak frequency: {res}"
    assert 5.5 <= hl <= 10.5, f"reported theta peak {hl} Hz is outside a plausible theta range"
    freq, power = _spectrum()
    assert freq is not None and len(freq) >= 5, "spectrum.csv lacks a (frequency, power) spectrum"


def test_proof_of_work_spectrum_matches_reference():
    ref = _reference()
    freq, power = _spectrum()
    pw.check_spectrum_matches_reference(freq, power, ref, band_corr_min=BAND_CORR_MIN,
                                        peak_tol=SELF_PEAK_TOL + 0.1)


def test_headline_is_movement_theta_and_self_consistent():
    ref = _reference()
    res = _results()
    freq, power = _spectrum()
    hl = _headline(res)
    lo, hi = PEAK_BAND
    assert hl is not None and lo <= hl <= hi, (
        f"reported theta peak frequency {hl} Hz is not the honest movement-related value "
        f"(~{ref['stats']['loco_peak']:.1f} Hz, band [{lo},{hi}]). A whole-recording spectrum that "
        f"does not condition on the animal's movement state peaks at ~7.9 Hz (slow REM/immobility "
        f"theta) and understates the theta frequency.")
    sub_peak = pw.band_peak(freq, power)
    assert abs(hl - sub_peak) <= SELF_PEAK_TOL, (
        f"the reported theta peak ({hl} Hz) does not equal the peak of the submitted spectrum "
        f"({sub_peak:.2f} Hz); results.json and spectrum.csv disagree")


def test_state_dependence_recognised():
    """Discriminating judgement, fail if absent (DEVCONN way): the honest analysis recognises that
    the theta peak frequency is state-dependent -- either by reporting the slower non-movement /
    whole-recording peak (~7.9 Hz) as a contrast, or by stating it in the write-up. A flat single
    number presented as the state-independent theta frequency misses what this result has."""
    ref = _reference()
    res = _results()
    whole_ref = float(ref["stats"]["whole_peak"])
    hl = _headline(res) or 9.0
    # (a) a volunteered slower peak (whole-recording / rest / REM / immobility), ~1 Hz below headline
    slow_vals = pw.find_all_numbers(
        res, [r"whole", r"rest", r"rem", r"immobil", r"sleep", r"quiet", r"nonmov", r"stationary",
              r"allrecord", r"overallpeak", r"contrast"],
        exclude=[r"band", r"channel", r"nperseg", r"window", r"rate", r"time", r"threshold"])
    has_slow_number = any(6.8 <= v <= 8.4 and (hl - v) >= 0.6 for v in slow_vals)
    # (b) prose recognising state-dependence
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower() if (OUT / "findings.md").exists() else ""
    STATE = (r"state[- ]?depend|movement|locomot|running|run\b|awake|immobil|rest\b|sleep|rem\b|"
             r"quiescen|behavioural state|behavioral state|speed")
    SLOW = (r"slow\w*|lower|~?7\.\d|7\.\d ?hz|whole[- ]?record|entire record|overall|drag\w*|"
            r"pull\w*|understate|reduc\w*|decreas\w*|down\b")
    prose = bool(re.search(STATE + r"[^\n]{0,120}(?:" + SLOW + ")", text) or
                 re.search("(?:" + SLOW + r")[^\n]{0,120}(?:" + STATE + ")", text) or
                 re.search(r"theta[^\n]{0,60}(?:faster|slower|higher|lower)[^\n]{0,60}(?:" + STATE + ")", text))
    assert has_slow_number or prose, (
        "the submission does not recognise that the hippocampal theta peak frequency is "
        "state-dependent. Theta during locomotion (~9 Hz) is ~1.5 Hz faster than during REM / "
        "awake immobility (~7.5 Hz); a whole-recording spectrum on this mostly-rest session is "
        f"dragged down to ~{whole_ref:.1f} Hz. Reporting a single number as the state-independent "
        "theta frequency, with no recognition of the movement/rest dependence, misses the issue.")
