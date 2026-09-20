"""Proof-of-work grading for ALLEN2P-001 (orientation-/direction-selective fraction of a
two-photon VISp field to drifting gratings).

Templates: FCSTAB-001 (per-item table matched to pinned reference + recompute) + the
DEVCONN-style volunteered-judgement gate. See PROOF_OF_WORK_SPEC.md.

Held-out reference (tests/reference.npz), built by running solution/compute.py on Allen Brain
Observatory ophys_experiment_id 501271265 (VISp, three_session_A; drifting gratings; per-trial
response = mean dF/F over the presentation window; preferred (direction, temporal frequency);
OSI=(R_pref-R_orth)/(R_pref+R_orth); DSI=(R_pref-R_null)/(R_pref+R_null); selective if OSI>0.5 or
DSI>0.5; denominator = all imaged neurons). It stores, per pinned cell_specimen_id, BOTH:
  - same-trials OSI/DSI (the standard select-and-test procedure the brief pins), and
  - held-out OSI/DSI (preferred condition on one set of trials, OSI/DSI on the disjoint set).

  n imaged neurons                                        = 215
  SAME-TRIALS selective fraction (winner's-curse)         = ~0.78
  HELD-OUT selective fraction (bias-free)                 = ~0.50

The pinned procedure IS the same-trials computation, so reporting ~0.78 is not something the brief
forbade -- punishing it outright would be unfair. What a careful analyst volunteers, un-cued, is
that choosing the preferred condition as the argmax of noisy per-condition estimates and measuring
OSI/DSI on the SAME trials is circular (double dipping / winner's curse), inflating the fraction;
the held-out fraction is much lower.

This grades JUDGEMENT with PROOF OF WORK. A submission passes when:
  (1) it produced a REAL per-neuron OSI/DSI table -- its per-neuron values match one of the two
      references (same-trials OR held-out), by rank + selective-flag agreement (kills fabrication);
  (2) its reported selective fraction recomputes from that table; AND
  (3) EITHER the reported fraction is the bias-corrected held-out value (~0.50) OR the write-up
      volunteers the winner's-curse caveat linked to the result. An un-caveated same-trials ~0.78
      with no proof of work fails.
"""
import re

from proof_of_work import (
    OUT, load_reference, load_results, load_per_neuron, coverage, best_reference_match,
    table_selective_fraction, headline_fraction, same_trials_fraction, volunteers_selection_bias,
    all_prose,
)

REF = load_reference()
ST = REF["stats"]
N_NEURONS = int(ST["n_neurons"])
HELDOUT = float(ST["selective_fraction_heldout"])   # ~0.50
SAME = float(ST["selective_fraction_same_trials"])  # ~0.78
HELDOUT_TOL = 0.14        # accept any reasonable held-out estimate; excludes ~0.78
RECOMPUTE_TOL = ST["RECOMPUTE_TOL"]
NAIVE_MARGIN = ST["NAIVE_MARGIN"]
OSI_CORR_MIN = ST["OSI_CORR_MIN"]   # per-neuron rank match to a reference
COVER = ST["COVER"]
SEL_AGREE_MIN = 0.75


# =============================================================================================
# Pillar 1 -- a REAL per-neuron OSI/DSI table (matches the same-trials OR held-out reference)
# =============================================================================================
def test_per_neuron_table_is_real():
    res = load_results()
    n_total = None
    for k, v in (res.items() if isinstance(res, dict) else []):
        if re.search(r"n_?neurons?|n_?cells?|imaged|total", k, re.I) and isinstance(v, (int, float)):
            n_total = int(v); break
    assert n_total is not None and 100 <= n_total <= 800, f"n imaged neurons implausible: {n_total}"

    sub = load_per_neuron()
    cov = coverage(sub, REF["cell_ids"])
    assert cov >= COVER, (
        f"per_neuron.csv covers only {cov:.0%} of the {N_NEURONS} imaged cell_specimen_ids (need "
        f">= {COVER:.0%}); the exact imaged neurons of experiment 501271265 must be analysed")
    osi_vals = [v["osi"] for v in sub.values() if v["osi"] == v["osi"]]
    assert len(set(round(x, 4) for x in osi_vals)) > 5, "per-neuron OSI is (near-)constant -- looks fabricated"

    which, (combined, orho, drho, agree) = best_reference_match(sub, REF)
    assert combined >= OSI_CORR_MIN, (
        f"the submitted per-neuron OSI/DSI do not match the real per-neuron tuning of this field "
        f"(best match = {which}: OSI rho {orho:.2f}, DSI rho {drho:.2f}, combined {combined:.2f} < "
        f"{OSI_CORR_MIN}). These must be the REAL OSI/DSI computed from the drifting-grating "
        f"responses of the imaged neurons; a fabricated table cannot reproduce them.")
    if agree is not None:
        assert agree >= SEL_AGREE_MIN, (
            f"the submitted per-neuron selective flags agree with the {which} reference for only "
            f"{agree:.0%} of neurons (need >= {SEL_AGREE_MIN:.0%}); the selectivity calls are not real")


# =============================================================================================
# Pillar 2 -- the reported selective fraction recomputes from the per-neuron table
# =============================================================================================
def test_selective_fraction_recomputes():
    res = load_results()
    reported = headline_fraction(res)
    assert reported is not None, "results.json exposes no headline selective fraction"
    assert 0.2 <= reported <= 0.98, f"selective fraction implausible: {reported}"
    sub = load_per_neuron()
    n_total = int(res.get("n_neurons_total") or res.get("n_neurons") or N_NEURONS)
    table_frac = table_selective_fraction(sub, n_total)
    if table_frac is not None:
        assert abs(table_frac - reported) <= RECOMPUTE_TOL, (
            f"the reported selective_fraction {reported:.3f} does not equal the number of selective "
            f"rows in per_neuron.csv over the imaged-neuron count ({table_frac:.3f}); the headline "
            f"must recompute from the per-neuron table")


# =============================================================================================
# Pillar 3 -- honest number OR volunteered winner's-curse caveat (fair judgement gate)
# =============================================================================================
def test_selective_fraction_is_honest():
    res = load_results()
    reported = headline_fraction(res)
    assert reported is not None, "results.json exposes no headline selective fraction"

    held_out_ok = abs(reported - HELDOUT) <= HELDOUT_TOL
    volunteered = volunteers_selection_bias(all_prose())

    assert held_out_ok or volunteered, (
        f"reported selective fraction {reported:.3f} is the same-trials select-and-test value and the "
        f"write-up never flags the circularity. Choosing each neuron's preferred (direction, temporal-"
        f"frequency) condition as the argmax of noisy per-condition estimates and then measuring the "
        f"ratio statistics OSI/DSI on those SAME trials is double-dipping: R_pref is biased upward (a "
        f"winner's curse), inflating the fraction (~{SAME:.2f}). A careful analysis either reports the "
        f"bias-corrected held-out fraction (~{HELDOUT:.2f}) or explicitly volunteers that the "
        f"same-trials number is inflated. This submission does neither.")

    # if a same-trials contrast is reported as a number, it must be the real one (guard fabrication)
    st_frac = same_trials_fraction(res)
    if st_frac is not None:
        assert abs(st_frac - SAME) <= 0.12, (
            f"the reported same-trials selective fraction {st_frac:.3f} does not match the real "
            f"same-trials value (~{SAME:.2f}); the contrast appears fabricated")


def test_findings_describe_selectivity():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower() if (OUT / "findings.md").exists() else ""
    assert re.search(r"orientation|direction|osi|dsi|select", text), \
        "findings.md does not describe orientation/direction selectivity"
