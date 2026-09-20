"""Proof-of-work grader for N170PROFILE-001 (the ERP CORE N170 face effect at PO8).

Recut to the paper's actual N170 characterisation (Kappenman et al. 2021, Figure 2 /
Tables 1-3): the FULL N=37 analysis sample (subjects 1-40 excluding 1, 5, 16), the a priori
PO8 electrode, and the face-minus-car difference wave. The two headline measurements are the
SIGNED PO8 mean amplitude in 110-150 ms (the ERP CORE N170 amplitude score, a negative value)
and the 50% FRACTIONAL-PEAK onset latency (ERPLAB `fpeaklat`, negative polarity, peak in
10-150 ms; the pre-peak time at which the wave reaches 50% of its peak). Both are measured
PER SUBJECT and aggregated to a group mean + 95% CI.

The grade is carried by NUMBERS, not prose keywords, and by a held-out reference
(`reference.npz`) built by running the oracle on the exact 37-subject data:

  PILLAR 1  the submitted per-subject table must cover the exact 37-subject analysis sample,
            be non-constant, and match the held-out per-subject SIGNED values (no abs()).
  PILLAR 2  the group mean recomputed FROM the submitted rows must match BOTH the reference
            and the agent's reported headline number.
  PILLAR 3  the reported conclusion numbers (signed amplitude; 50%-fractional-peak onset; and,
            if the whole-scalp cluster test is reported, the corrected cluster p-value/mass)
            must match the reference. A naive analyst who reports an uncorrected/cluster
            "onset" (~35 / ~80 ms) or an abs amplitude cannot match these.

The whole-scalp cluster analysis is DESCRIPTIVE (cluster-level only); it is graded only if the
submission reports it. There is NO abs(amplitude) check and NO prose-keyword-only judgement.
"""
import json
import os
import re
from pathlib import Path

import numpy as np

import proof_of_work as pw

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF = np.load(Path(__file__).resolve().parent / "reference.npz", allow_pickle=False)

# ---- tolerances (documented; see proposal.md validation matrix) -------------------------
AMP_VAL_TOL = 0.40     # per-subject |submitted - ref| PO8 mean amplitude (uV); tight (robust measure)
AMP_GROUP_TOL = 0.30   # group-mean amplitude vs reference / reported (uV)
ONSET_VAL_TOL = 25.0   # per-subject |submitted - ref| onset (ms); loose (onset is noisier per subject)
ONSET_MATCH = 0.70     # fraction of subjects whose per-subject onset must match
ONSET_GROUP_TOL = 15.0 # group-mean onset vs reference / reported (ms) -- excludes cluster-onset (~74 ms)
# The descriptive cluster test is optional. If reported, its corrected p-value must show a real
# significant cluster and its mass must be the right order of magnitude (both are seed- and
# threshold-dependent, so these are deliberately lenient -- fabrication, not method variation,
# is what they catch).
CLUSTER_MASS_LO, CLUSTER_MASS_HI = 0.40, 2.5  # reported cluster mass in [lo, hi] * reference


def _load(name):
    p = OUT / name
    assert p.exists(), f"missing required output {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _submitted():
    csvp = OUT / "per_subject.csv"
    assert csvp.exists(), (
        "missing per_subject.csv -- the task requires SIGNED per-subject measurements "
        "(PO8 mean amplitude and 50% fractional-peak onset) for the 37-subject analysis sample")
    return pw.load_submitted(str(csvp), {
        "amp": ["amp_po8", "amp", "amplitude", "po8"],
        "onset": ["onset", "fractional", "latency", "onset_ms"],
    })[0]


# ---- PILLAR 3a: headline signed amplitude ----------------------------------------------
def test_headline_amplitude_is_signed_and_correct():
    data = _load("n170.json")
    assert str(data.get("electrode", "")).upper() == "PO8" or "po8" in json.dumps(data).lower(), \
        "n170.json must report the a priori PO8 electrode"
    n = int(data.get("n_subjects", 0))
    assert 34 <= n <= 40, f"expected the full ~37-subject analysis sample, got n_subjects={n}"
    amp = _num(data.get("amp_po8_uv"))
    ref_mean = float(REF["amp_mean"])
    assert amp is not None, "n170.json missing amp_po8_uv"
    assert amp < 0, (
        f"amp_po8_uv must be the SIGNED face-minus-car mean amplitude (a negative value); "
        f"got {amp} -- do not report abs amplitude")
    assert abs(amp - ref_mean) <= AMP_GROUP_TOL, (
        f"reported PO8 mean amplitude {amp:.3f} uV is not within {AMP_GROUP_TOL} of the "
        f"reference group mean {ref_mean:.3f} uV")


# ---- PILLAR 3b: headline 50%-fractional-peak onset --------------------------------------
def test_headline_onset_is_fractional_peak_latency():
    data = _load("n170.json")
    onset = _num(data.get("onset_latency_ms"))
    ref_mean = float(REF["onset_mean"])
    assert onset is not None, "n170.json missing onset_latency_ms"
    assert abs(onset - ref_mean) <= ONSET_GROUP_TOL, (
        f"reported onset {onset:.1f} ms is not within {ONSET_GROUP_TOL} ms of the reference "
        f"50%-fractional-peak onset {ref_mean:.1f} ms. It must be the paper's fractional-peak "
        f"onset -- not an uncorrected point-wise 'first significant sample' (~{float(REF['naive_onset']):.0f} ms) "
        f"or a cluster-onset.")
    # explicitly distinct from the spurious uncorrected onset
    assert onset > float(REF["naive_onset"]) + 20, (
        "the reported onset coincides with the uncorrected point-wise 'first significant sample', "
        "which is a multiple-comparisons false positive, not the 50%-fractional-peak onset")


# ---- PILLAR 1 + 2: per-subject SIGNED amplitude proof of work ----------------------------
def test_per_subject_amplitude_proof_of_work():
    sub = _submitted()
    present = pw.check_subjects_and_values(
        sub, REF["ref_ids"], REF["ref_amp"], "amp", AMP_VAL_TOL,
        cover=0.90, match=0.90, eps=1e-3, signed=True)
    reported = _num(_load("n170.json").get("amp_po8_uv"))
    pw.check_recompute(sub, present, "amp", float(REF["amp_mean"]), reported,
                       tol_ref=AMP_GROUP_TOL, tol_report=AMP_GROUP_TOL)


# ---- PILLAR 1 + 2: per-subject onset proof of work --------------------------------------
def test_per_subject_onset_proof_of_work():
    sub = _submitted()
    present = pw.check_subjects_and_values(
        sub, REF["ref_ids"], REF["ref_onset"], "onset", ONSET_VAL_TOL,
        cover=0.90, match=ONSET_MATCH, eps=1.0, signed=True)
    reported = _num(_load("n170.json").get("onset_latency_ms"))
    pw.check_recompute(sub, present, "onset", float(REF["onset_mean"]), reported,
                       tol_ref=ONSET_GROUP_TOL, tol_report=ONSET_GROUP_TOL)


# ---- PILLAR 3c: descriptive cluster stat, only if reported ------------------------------
def test_cluster_stat_if_reported():
    data = _load("n170.json")
    cl = data.get("cluster_level_only") or data.get("cluster") or {}
    if not isinstance(cl, dict) or not cl:
        return  # cluster analysis is optional/descriptive; nothing reported -> nothing to grade
    pvals = cl.get("cluster_pvals")
    pmin = cl.get("min_cluster_pval")
    if pmin is None and isinstance(pvals, list) and pvals:
        nums = [_num(p) for p in pvals if _num(p) is not None]
        pmin = min(nums) if nums else None
    if pmin is None:
        # no corrected p-value present (e.g. cluster not run / only a descriptive note) ->
        # nothing to grade; the headline (amplitude + onset) carries the result
        return
    pmin = _num(pmin)
    assert pmin is not None and 0.0 <= pmin <= 0.05, (
        f"reported cluster is not a real corrected-significant cluster (p={pmin}); a retained "
        f"whole-scalp cluster analysis must report a corrected cluster p-value <= 0.05")
    mass = _num(cl.get("cluster_mass"))
    if mass is not None:
        ref_mass = float(REF["cluster_mass"])
        assert CLUSTER_MASS_LO * ref_mass <= mass <= CLUSTER_MASS_HI * ref_mass, (
            f"reported cluster mass {mass} is not the right order of magnitude vs the reference "
            f"{ref_mass:.1f} (expected within [{CLUSTER_MASS_LO}, {CLUSTER_MASS_HI}]x)")


# ---- SECONDARY (not the sole gate): the write-up actually reports the profile ------------
def test_findings_reports_profile():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert ("po8" in text or "posterior" in text) and ("n170" in text or "face" in text), \
        "findings.md does not report the face-minus-car N170 profile at PO8"
    amp = _num(_load("n170.json").get("amp_po8_uv"))
    nums = [float(x) for x in re.findall(r"-?\d+\.\d+", text)]
    assert any(abs(abs(n) - abs(amp)) < 0.6 for n in nums), \
        "findings.md does not report a PO8 amplitude consistent with n170.json"
