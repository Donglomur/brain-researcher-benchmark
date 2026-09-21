"""Proof-of-work grader for ERRMON-001 (error-related frontocentral negativity, ERP CORE Flankers).

Single-subject, single-value task: the deliverable is one error-minus-correct amplitude at FCz.
A lone scalar is guessable, so (RESTCONN-001 / QSMDIPOLE-001 model) the grader also validates
the finest intermediate the analysis naturally produces -- the FCz error-average and
correct-average waveforms -- against a held-out reference (tests/reference.npz, built from the
oracle run, never shipped to the agent), recomputes the window ERN FROM the submitted
waveforms, and grades the ERN as a number.

Held-out ground truth (ERP CORE Flankers subject 001; average reference; 0.1-30 Hz; pre-event
baseline; mean FCz amplitude over 0-100 ms, error minus correct):
  response-locked (the ERN)  = -5.9 uV   <-- honest (the button-press-locked component)
  stimulus-locked            = -0.58 uV  (naive; the response-time jitter smears the ERN)
The response- and stimulus-locked FCz difference waveforms are essentially uncorrelated
(r ~ -0.13), so a stimulus-locked or fabricated waveform fails the waveform match; only the
real response-locked waveforms recompute to the ~-5.9 uV negativity.
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

ERR_CORR = 0.80        # submitted FCz error waveform vs held-out reference
DIFF_CORR = 0.75       # submitted error-minus-correct difference waveform vs reference
ERN_TOL_REF = 2.5      # recomputed window ERN vs reference (-5.9)
ERN_TOL_JSON = 2.0     # recomputed window ERN vs reported (CSV<->JSON)
ERN_MAX = -2.5         # ERN must be a clear negativity; stimulus-locked (-0.58) fails
WIN = (0.0, 0.1)


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference_errmon(REF_PATH)


def _load_json(name):
    p = OUT / name
    assert p.exists(), f"missing required output {name}"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"{name} is not valid JSON: {e}")


def _submitted():
    p = OUT / "fcz_waveforms.csv"
    assert p.exists(), (
        "missing required output fcz_waveforms.csv -- the FCz error-average and correct-average "
        "waveforms (one row per epoch time). The single ERN amplitude cannot be validated "
        "without the fine-grained waveforms it is measured from.")
    t, e, c = pw.load_submitted_waveforms(p)
    assert t is not None and len(t) >= 40, (
        "fcz_waveforms.csv could not be parsed into (time, error, correct) waveforms")
    return t, e, c


def _reported_ern(cj):
    return pw.find_number(cj, [r"ernamplitude", r"ern", r"errorminuscorrect", r"amplitudeuv",
                               r"amplitude", r"ernuv"],
                          exclude=[r"stimulus", r"reference", r"naive", r"window", r"ms", r"error_?trial",
                                   r"correct", r"ntrial", r"count", r"electrode", r"nerror"])


def test_outputs_present_and_wellformed():
    _reference()
    cj = _load_json("ern.json")
    ern = _reported_ern(cj)
    assert ern is not None, f"ern.json lacks a reported ERN amplitude: {cj}"
    assert 1.0 <= abs(ern) <= 20.0, (
        f"reported ERN {ern} uV is implausible for the response-locked value (~-5.9 uV)")
    _submitted()


# ---------------------------------------------------------------- pillar 1
def test_proof_of_work_waveforms_match_reference():
    ref = _reference()
    t, e, c = _submitted()
    import statistics
    assert statistics.pstdev(e.tolist()) > 1e-4, (
        "the submitted FCz error waveform is constant -- not a real evoked average")
    rt, ev = pw.interp_series(t, e, ref["times"])
    assert len(ev) >= 40, "submitted waveforms do not overlap the epoch enough to validate"
    ref_err = ref["error"][(ref["times"] >= rt.min()) & (ref["times"] <= rt.max())]
    ce = pw.pearson(ev, ref_err)
    assert ce == ce and ce >= ERR_CORR, (
        f"the submitted FCz error waveform does not track the held-out reference (r={ce:.3f} "
        f"< {ERR_CORR}); it was not computed from the real response-locked epochs.")
    # the error-minus-correct DIFFERENCE waveform (the ERN signature) must also track the
    # reference -- a stimulus-locked difference waveform is nearly uncorrelated (r ~ -0.13).
    _, dv = pw.interp_series(t, e - c, ref["times"])
    ref_diff = (ref["error"] - ref["correct"])[
        (ref["times"] >= rt.min()) & (ref["times"] <= rt.max())]
    cd = pw.pearson(dv, ref_diff)
    assert cd == cd and cd >= DIFF_CORR, (
        f"the submitted error-minus-correct difference waveform does not track the held-out "
        f"reference (r={cd:.3f} < {DIFF_CORR}); a stimulus-locked or fabricated waveform does "
        f"not reproduce the response-locked ERN time course.")


# ---------------------------------------------------------------- pillar 2
def test_recompute_window_ern():
    ref = _reference()
    t, e, c = _submitted()
    cj = _load_json("ern.json")
    ern_rows = pw.window_mean(t, e - c, WIN)
    ern_ref = float(ref["stats"]["ern_response_window"])
    assert ern_rows == ern_rows, "could not recompute the ERN window from the submitted waveforms"
    assert abs(ern_rows - ern_ref) <= ERN_TOL_REF, (
        f"the window ERN recomputed from the submitted waveforms ({ern_rows:.2f} uV) does not "
        f"match the held-out reference ({ern_ref:.2f} uV, tol {ERN_TOL_REF}); the waveforms are "
        f"not the real response-locked analysis.")
    reported = _reported_ern(cj)
    assert reported is not None and abs(abs(ern_rows) - abs(reported)) <= ERN_TOL_JSON, (
        f"the ERN recomputed from the waveforms ({ern_rows:.2f} uV) does not match the reported "
        f"value ({reported}); the waveforms and ern.json disagree.")


# ---------------------------------------------------------------- pillar 3 (ERN as a number)
def test_ern_is_response_locked_negativity():
    ref = _reference()
    t, e, c = _submitted()
    ern_rows = pw.window_mean(t, e - c, WIN)
    assert ern_rows <= ERN_MAX, (
        f"the error-minus-correct FCz amplitude recomputed from the submitted waveforms is "
        f"{ern_rows:.2f} uV -- not the pronounced negativity of the ERN (~-5.9 uV). A near-zero "
        f"value is the stimulus-locked average, in which the response-time jitter smears the "
        f"error negativity.")
    stim = float(ref["stats"]["ern_stimulus_window"])
    resp = float(ref["stats"]["ern_response_window"])
    assert abs(ern_rows - resp) < abs(ern_rows - stim), (
        f"the recomputed ERN ({ern_rows:.2f} uV) is closer to the stimulus-locked value "
        f"({stim:.2f} uV) than to the response-locked ERN ({resp:.2f} uV).")


# ---------------------------------------------------------------- secondary prose signal
def test_findings_report_secondary():
    """SECONDARY (the numeric pillars carry the grade): findings.md reports an ERN of a
    magnitude consistent with ern.json."""
    p = OUT / "findings.md"
    text = p.read_text(encoding="utf-8").lower() if p.exists() else ""
    assert text, "findings.md missing or empty"
    assert ("error" in text) and ("negativ" in text or "ern" in text or "fcz" in text), \
        "findings.md does not report an error-related negativity"
    ern = _reported_ern(_load_json("ern.json"))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.?\d*", text)]
    assert any(abs(n - abs(ern)) < 2.0 for n in nums), \
        "findings.md does not report an ERN magnitude consistent with ern.json"
