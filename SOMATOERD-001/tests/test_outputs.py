"""Proof-of-work grader for SOMATOERD-001 (contralateral sensorimotor beta ERD, MNE somato).

Single-subject, single-value task: the deliverable is one beta-ERD percentage. A lone scalar
is guessable, so (RESTCONN-001 / QSMDIPOLE-001 model) the grader also validates the finest
intermediate the analysis naturally produces -- the contralateral sensorimotor beta-band
power time course (percent baseline, one value per epoch time sample) -- against a held-out
reference (tests/reference.npz, built from the oracle run, never shipped to the agent),
recomputes the window ERD FROM the submitted curve, and grades the ERD as a number.

Held-out ground truth (somato sub-01, 111 trials; gradiometers MEG 1342/1343/1332/1333;
Morlet 15-30 Hz, n_cycles=freq/2; percent baseline -1.0..-0.25 s; beta 15-30 Hz over the
0.10-0.35 s window):
  induced/total power (per-trial TFR then averaged)  window ERD = -17.7%   <-- honest
  evoked power (TFR of the trial-average)            window     = +443.6%  (naive)
The induced and evoked beta-power curves are essentially uncorrelated (r ~ -0.07): the naive
evoked curve is a large POSITIVE excursion, so it fails the time-course match; only the real
induced curve tracks the held-out reference and recomputes to the modest negative ERD.
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

TS_CORR = 0.85          # submitted beta-power curve vs held-out induced reference
ERD_TOL_REF = 12.0      # recomputed window ERD vs reference (-17.7)
ERD_TOL_JSON = 8.0      # recomputed window ERD magnitude vs reported (CSV<->JSON)
ERD_MAX = -5.0          # window ERD must be a clear decrease (<= -5%); evoked (+444%) fails
WIN = (0.10, 0.35)


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _load_json(name):
    p = OUT / name
    assert p.exists(), f"missing required output {name}"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"{name} is not valid JSON: {e}")


def _submitted():
    p = OUT / "beta_power_timecourse.csv"
    assert p.exists(), (
        "missing required output beta_power_timecourse.csv -- the contralateral sensorimotor "
        "beta-band power (percent baseline) at each epoch time. The single ERD cannot be "
        "validated without the fine-grained time course it is measured from.")
    t, v = pw.load_submitted_timecourse(p)
    assert t is not None and len(t) >= 50, (
        "beta_power_timecourse.csv could not be parsed into a (time, beta-power) series")
    return t, v


def _reported_erd(cj):
    return pw.find_number(cj, [r"betaerd", r"erd", r"desync", r"betapercent", r"erdpercent",
                               r"betaerdpercent"],
                          exclude=[r"evoked", r"reference", r"naive", r"window", r"ms", r"band",
                                   r"hz", r"trial", r"channel", r"freq", r"cycle", r"baseline"])


def test_outputs_present_and_wellformed():
    _reference()
    cj = _load_json("erd.json")
    erd = _reported_erd(cj)
    assert erd is not None, f"erd.json lacks a reported beta-ERD percentage: {cj}"
    assert 3.0 <= abs(erd) <= 60.0, (
        f"reported beta ERD {erd}% is implausible for the induced-power value (~-17.7%); "
        f"the evoked-power artefact is ~+444%")
    t, v = _submitted()


# ---------------------------------------------------------------- pillar 1
def test_proof_of_work_timecourse_matches_reference():
    ref = _reference()
    t, v = _submitted()
    import statistics
    assert statistics.pstdev(v.tolist()) > 1e-6, (
        "the submitted beta-power time course is constant -- not a real TFR extraction")
    rt, rv, sv = pw.interp_to_ref(t, v, ref["times"])
    assert len(rv) >= 50, (
        "the submitted time course does not overlap the analysis epoch enough to validate")
    # restrict the reference curve to the same overlap grid
    ref_on_grid = ref["tc"][(ref["times"] >= rt.min()) & (ref["times"] <= rt.max())]
    c = pw.pearson(sv, ref_on_grid)
    assert c == c and c >= TS_CORR, (
        f"the submitted beta-power time course does not track the held-out induced reference "
        f"(r={c:.3f} < {TS_CORR}); it was not computed from the real per-trial time-frequency "
        f"power. The naive evoked-power curve is a large positive excursion (r ~ -0.07 with the "
        f"reference).")


# ---------------------------------------------------------------- pillar 2
def test_recompute_window_erd():
    ref = _reference()
    t, v = _submitted()
    cj = _load_json("erd.json")
    erd_rows = pw.window_mean(t, v, WIN)
    erd_ref = float(ref["stats"]["erd_induced_window"])
    assert erd_rows == erd_rows, "could not recompute the ERD window from the submitted curve"
    assert abs(erd_rows - erd_ref) <= ERD_TOL_REF, (
        f"the window ERD recomputed from the submitted curve ({erd_rows:.1f}%) does not match "
        f"the held-out reference ({erd_ref:.1f}%, tol {ERD_TOL_REF}); the curve is not the real "
        f"induced-power analysis.")
    reported = _reported_erd(cj)
    assert reported is not None and abs(abs(erd_rows) - abs(reported)) <= ERD_TOL_JSON, (
        f"the ERD recomputed from the curve ({erd_rows:.1f}%) does not match the reported value "
        f"({reported}); the time course and erd.json disagree.")


# ---------------------------------------------------------------- pillar 3 (ERD as a number)
def test_erd_is_a_decrease_not_the_evoked_artifact():
    ref = _reference()
    t, v = _submitted()
    erd_rows = pw.window_mean(t, v, WIN)
    assert erd_rows <= ERD_MAX, (
        f"the window beta power recomputed from the submitted curve is {erd_rows:.1f}% -- not a "
        f"desynchronization (decrease). An event-related DESYNCHRONIZATION is a power DROP; a "
        f"large positive value is the evoked-power artefact (TFR of the trial-average), the "
        f"wrong sign.")
    evoked = float(ref["stats"]["erd_evoked_window"])
    assert abs(erd_rows - float(ref["stats"]["erd_induced_window"])) < abs(erd_rows - evoked), (
        f"the recomputed window value ({erd_rows:.1f}%) is closer to the naive evoked-power "
        f"artefact ({evoked:.0f}%) than to the induced-power ERD.")


# ---------------------------------------------------------------- secondary prose signal
def test_findings_report_secondary():
    """SECONDARY (the numeric pillars carry the grade): findings.md reports a beta ERD of a
    magnitude consistent with erd.json."""
    p = OUT / "findings.md"
    text = p.read_text(encoding="utf-8").lower() if p.exists() else ""
    assert text, "findings.md missing or empty"
    assert ("beta" in text) and ("erd" in text or "desync" in text), \
        "findings.md does not report a beta ERD / desynchronization"
    erd = _reported_erd(_load_json("erd.json"))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.?\d*", text)]
    assert any(abs(n - abs(erd)) < 3.0 for n in nums), \
        "findings.md does not report an ERD magnitude consistent with erd.json"
