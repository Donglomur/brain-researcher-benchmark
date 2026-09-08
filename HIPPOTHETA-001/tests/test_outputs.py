"""Grading checks for HIPPOTHETA-001 (the hippocampal theta peak frequency).

Ground truth (validated before release on DANDI 000552, sub-e15-13f1 ses-e15-13f1-220117; LFP
processing/ecephys/LFP/ElectricalSeriesLFP at 1250 Hz; running speed from
processing/behavior/SubjectPosition; best theta-power channel; Welch 4 s windows; 6-10 Hz band):

  MOVEMENT (running, speed > ~5 units/s) : ~9.0 Hz  (>3 -> 8.86; stable across channel)  <-- honest
  WHOLE RECORDING, no state conditioning : ~7.9 Hz  (naive)
  (context) REM theta ~7.4 Hz ; awake immobility theta ~7.5 Hz

Theta frequency is STATE-DEPENDENT: running (movement) theta is fast (~9 Hz), whereas theta during
REM sleep and awake immobility is ~1.5 Hz slower (~7.4-7.5 Hz). This session is a ~7 h recording
that is mostly home-cage rest/sleep with a single ~31 min maze epoch, so a theta-band spectral peak
taken over the WHOLE recording (or otherwise not conditioned on the animal's behavioural state) is
dragged down to ~7.9 Hz by the dominant slow-theta (REM / immobility) periods. Only conditioning on
movement recovers the ~9 Hz movement-related theta.

The failure mode this task targets (un-cued, over-claim of a single identity -- cf. GRADIENT-001):
the agent estimates one theta peak over the whole LFP, asserts a single flat frequency (~7.9 Hz),
and never asks whether it depends on the animal's behavioural state -- when it does. A mature
analyst VOLUNTEERS the state-conditioning (the task never mentions movement, speed, state, or REM),
recovers the ~9 Hz movement theta, and reports the frequency as state-dependent. A flat
whole-recording ~7.9 Hz, with no conditioning on state, over-claims and fails the checks below.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED_MOVE = 8.9      # movement (running) theta peak frequency (Hz)
TOL = 0.55               # [8.35, 9.45]: passes the ~8.86-9.0 movement peak; fails the ~7.9 whole-recording value
THETA_LO, THETA_HI = 6.0, 10.0

# keys/labels that denote a NON-headline contrast quantity (never grade these as the reported value)
EXCLUDE = re.compile(r"whole|recording|session|rem|immobil|rest|sleep|slow|naive|"
                     r"contaminat|contrast|context|delta|non.?theta|quiescen|still|stationary", re.I)
PEAK_KEY = re.compile(r"(theta.*(peak|freq))|((peak|dominant).*(theta|freq))|theta_peak|peak_freq", re.I)

# --- prose tokens ---
THETA = r"(?:theta|\b6[\-– ]?10\s*hz|\btheta[- ]?band)"
# behavioural-state / movement conditioning terms
MOVE = (r"(?:locomot\w*|running|\brun\b|\bruns\b|\brunning\b|\bmoving\b|movement|ambulat\w*|"
        r"active behav\w*|active[- ]?state|\bspeed\b|velocit\w*)")
RESTLIKE = (r"(?:rest\w*|immobil\w*|quiescen\w*|\bstill\b|stationary|\brem\b|sleep|awake immobil\w*|"
            r"non[- ]?theta|slow[- ]?theta)")
# a term that signals genuine CONDITIONING / COMPARISON of the theta estimate -- deliberately
# NOT bare "during"/"while" (those collide with context prose like "freely moving during the
# session"); it must be an action on the estimate or a cross-state comparison.
COND = (r"(?:when the (?:mouse|animal) (?:was |is )?(?:running|moving|locomot|immobil|still|at rest)|"
        r"restrict\w*|condition\w*|gate[d]?|gating|segment\w*|only (?:the )?(?:running|movement|locomot)|"
        r"period[s]? (?:of|when)|during (?:running|locomot|movement|immobil|rest|rem)|"
        r"while (?:running|locomot|moving|immobil|the (?:mouse|animal))|speed\s*[>≥]|speed threshold|"
        r"compar\w*|versus|\bvs\.?\b|faster|slower|higher|lower|increase\w*|differ\w*|depend\w*|"
        r"state[- ]?dependent|state[- ]?depend\w*)")


def _load(name):
    p = OUT / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _results():
    return json.loads(_load("results.json"))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _walk(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def _headline_peak(res):
    """The reported theta peak: a theta-peak-frequency value NOT tagged as a contrast quantity
    (whole-recording / REM / immobility / rest / ...)."""
    for k, v in _walk(res):
        leaf = k.split(".")[-1].split("[")[0]
        if _num(v) and PEAK_KEY.search(leaf) and not EXCLUDE.search(k):
            if THETA_LO - 2.0 <= float(v) <= THETA_HI + 2.0:
                return float(v)
    for k, v in _walk(res):
        if _num(v) and re.search(r"freq|hz|peak", k, re.I) and not EXCLUDE.search(k):
            if THETA_LO <= float(v) <= THETA_HI:
                return float(v)
    return None


def _prose():
    """All submitted prose/metadata, lower-cased (findings + run_metadata + results)."""
    return "\n".join(_load(n) for n in ("findings.md", "run_metadata.json", "results.json")).lower()


def _conditioned_on_state():
    """True if the submission resolved theta by movement / behavioural state, rather than
    reporting a single whole-recording spectrum. Accepts a structured multi-condition report or
    prose that conditions/compares theta across movement/rest states (co-occurrence guarded so a
    bare 'running an eight-maze' context mention does not count)."""
    # 1) structured: >=2 theta-peak-like values on movement/rest-labelled keys
    res = _results()
    labelled = 0
    for k, v in _walk(res):
        if _num(v) and re.search(r"freq|hz|peak|theta", k, re.I) and \
           re.search(r"run|locomot|move|moving|speed|rest|immobil|rem|awake|state|still|quiescen|whole|session", k, re.I):
            if THETA_LO - 2.0 <= float(v) <= THETA_HI + 2.0:
                labelled += 1
    if labelled >= 2:
        return True
    # 2) prose: theta co-occurring with a movement/rest term AND a conditioning/comparison term
    text = _prose()
    for m in re.finditer(THETA, text):
        w = text[max(0, m.start() - 160): m.end() + 160]
        if (re.search(MOVE, w) or re.search(RESTLIKE, w)) and re.search(COND, w):
            # guard: the maze-running *context* ("running an eight-maze") alone is not conditioning
            if re.search(r"run\w*\s+(?:an?\s+)?(?:eight|8)[- ]?maze", w) and not re.search(
                    r"speed|locomot|immobil|rest|rem|during running|while running|running period|"
                    r"movement period|state[- ]?depend|faster|slower|conditioned|restrict|gated", w):
                continue
            return True
    return False


def test_theta_computed():
    res = _results()
    peak = _headline_peak(res)
    assert peak is not None, "results.json exposes no theta peak frequency (Hz) headline value"
    assert THETA_LO - 1.0 <= peak <= THETA_HI + 1.0, f"peak {peak} is not a plausible theta frequency"
    assert "theta" in _load("findings.md").lower(), "findings.md does not mention theta"


def test_theta_frequency_conditioned_on_behavioural_state():
    # The volunteered judgement (un-cued): theta frequency is state-dependent, so a single
    # whole-recording spectrum over a mostly-sleep session mis-states it. A mature analysis
    # conditions on the animal's movement / behavioural state. (cf. GRADIENT-001's robustness check.)
    # A movement-value headline (~8.4-9.5 Hz) is itself evidence of conditioning: the whole
    # recording, REM and immobility all peak <= 7.9 Hz, so only conditioning recovers a ~9 Hz peak.
    peak = _headline_peak(_results())
    numeric_evidence = peak is not None and 8.4 <= peak <= 9.5
    assert _conditioned_on_state() or numeric_evidence, (
        "the submission reported a single theta peak without conditioning on the animal's movement "
        "or behavioural state. Theta frequency is state-dependent (running ~9 Hz vs REM/immobility "
        "~7.5 Hz), and this session is mostly rest/sleep, so an un-conditioned whole-recording "
        "spectrum understates the movement-related theta frequency.")


def test_reports_movement_theta_not_flat_contaminated():
    # Having conditioned on state, the honest reported theta peak is the movement value (~9 Hz).
    # A flat whole-recording ~7.9 Hz (dragged down by the dominant REM/immobility slow theta) fails.
    res = _results()
    peak = _headline_peak(res)
    text = _prose()
    # numeric route: the headline peak reproduces the movement value
    numeric_ok = peak is not None and abs(peak - EXPECTED_MOVE) <= TOL
    # recognition route: prose states the running/movement theta is fast (~8.5-9.5) AND slower at rest
    fast_vals = [float(x) for x in re.findall(r"(\d\.?\d*)\s*hz", text)]
    says_fast_move = bool(re.search(MOVE, text)) and any(8.4 <= v <= 9.6 for v in fast_vals) and \
        bool(re.search(r"faster|fast\b|higher|~?\s*9\s*hz|state[- ]?depend|slower (?:at|during|in)|"
                       r"(?:rem|immobil|rest)\w*[^.\n]{0,40}(?:slow|7\.[0-9])", text))
    assert numeric_ok or says_fast_move, (
        f"reported theta peak {peak} Hz does not reproduce the movement-related value "
        f"{EXPECTED_MOVE:.1f} +/- {TOL:.1f} Hz, and the write-up does not report the faster "
        f"(~9 Hz) running theta distinct from the slower (~7.5 Hz) rest/REM theta. A ~7.9 Hz "
        f"whole-recording estimate understates the movement theta and over-claims a single "
        f"state-independent frequency.")
