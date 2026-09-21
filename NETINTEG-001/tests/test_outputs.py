"""Proof-of-work grader for NETINTEG-001 -- rank ADHD-200 participants by network
integration (global efficiency), an un-cued absolute-vs-density-matched thresholding
judgement.

The previous verifier used a non-constant guard + a pinned top-k set contrast, but never
checked that the submitted per-participant efficiency values are the REAL ones, never
recomputed the confound statistic from the rows, and graded the discriminating numbers only
as an optional fallback. This grader closes that: it validates the exact ADHD-200
participants and their per-participant density-matched efficiency against a reference
(tests/reference.npz, built from the oracle run; held out of the agent CONTAINER but PUBLIC in
this repo (burned) -- a real eval needs fresh tasks / a server-side reference), recomputes
the efficiency<->overall-connectivity-strength confound correlation FROM the submitted rows,
cross-checks it against the reported value and the reference, and grades the scientific
judgement AS NUMBERS: the confound is strongly POSITIVE under an absolute cutoff (~+0.86) and
weak/negative under a density-matched threshold (~-0.57), the two rankings are near-disjoint,
and the reported most-integrated set is the density-matched one. Keyword prose is secondary.
"""
import json
import os
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference.npz"


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _load(name):
    p = OUT / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _submitted():
    p = OUT / "efficiency.csv"
    assert p.exists(), "missing required output efficiency.csv"
    # Prefer a POSITIVE/absolute connectivity-strength proxy (mean positive FC, clipped mean
    # connectivity). Signed mean FC is centred to ~0 under global-signal regression and cannot
    # express the density confound, so it is intentionally NOT among the candidates.
    return pw.load_submitted(
        p,
        id_cols=("participant", "subject", "subjectid", "participantid", "subid", "id"),
        eff_cols=("globalefficiency", "efficiency", "geff", "eglob", "ge"),
        conn_cols=("meanpositivefc", "positivefc", "meanposfc", "posfc",
                   "meanpositiveconnectivity", "positivestrength", "positiveconnectivity",
                   "meanconnectivity", "meanconn", "connectivitystrength", "overallstrength",
                   "strength", "meanedge"))


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    sub = _submitted()
    effs = [e for e, _ in sub.values()]
    assert len(effs) >= 10, (
        f"efficiency.csv must carry per-participant global efficiency; parsed {len(effs)} rows")
    assert all(0.0 < v < 1.0 for v in effs), "global efficiency out of (0,1) for a binary graph"
    assert statistics.pstdev(effs) > 1e-4, (
        "global efficiency is identical across participants -- not computed per subject")


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_subjects_and_values():
    ref = _reference(); st = ref["stats"]
    sub = _submitted()
    pw.check_subjects_and_values(sub, ref, eff_tol=st["VAL_TOL"], corr_min=st["CORR_MIN"],
                                 cover=st["COVER"], match=st["MATCH"], eps=st["EPS"])


# ------------------------------------------------------------------ pillar 2
def test_recompute_confound_and_ranking_from_rows():
    """Recompute FROM the submitted rows: (always) the reported most-integrated ranking must be
    what the efficiency column actually produces (CSV<->JSON consistency); and IF a
    per-participant overall connectivity-strength column is present, the efficiency<->strength
    correlation recomputed from the rows must match the density-matched reference (~-0.57)."""
    ref = _reference(); st = ref["stats"]
    sub = _submitted()
    matched = [i for i in sub if i in set(ref["ids"])]

    # (a) CSV <-> reported ranking consistency (needs only the efficiency column)
    top = _reported_top_set()
    if top:
        ranked = sorted(matched, key=lambda i: sub[i][0], reverse=True)[:len(top)]
        overlap = len(set(ranked) & top)
        assert overlap >= 0.5 * len(top), (
            f"the reported most-integrated set does not match the ranking the submitted "
            f"efficiency column produces (overlap {overlap}/{len(top)}); CSV and reported "
            f"ranking are inconsistent.")

    # (b) if a per-participant connectivity-STRENGTH proxy is reported, recompute the density
    # confound. Grade the density-matched SIGNATURE -- a strongly NEGATIVE efficiency<->strength
    # correlation -- rather than a pinned magnitude, so a defensible strength proxy (mean
    # positive FC vs clipped mean connectivity) or density range is not penalised. The real
    # value is ~-0.57 to -0.69 against a positive-strength proxy; an absolute-threshold
    # submission instead recomputes a strongly POSITIVE value (~+0.89), because under a fixed
    # cutoff a participant's graph density is set by its overall connectivity strength.
    conns = [sub[i][1] for i in matched]
    if sum(1 for c in conns if c == c) >= 0.9 * len(matched) and len(matched) >= 10:
        eff_ok = [sub[i][0] for i in matched if sub[i][1] == sub[i][1]]
        conn_ok = [sub[i][1] for i in matched if sub[i][1] == sub[i][1]]
        r_rows = pw.pearson(eff_ok, conn_ok)
        thr = float(st["POS_CONFOUND_MAX"])
        assert r_rows <= thr, (
            f"efficiency<->overall-strength correlation recomputed from the submitted rows "
            f"({r_rows:+.3f}) is not the strongly-negative density-matched signature "
            f"(<= {thr:+.2f}; on this data it is ~{st['dm_strength_corr_pos']:+.2f} against a "
            f"positive-strength proxy). A fixed-absolute-threshold efficiency recomputes a "
            f"strongly POSITIVE correlation (~{st['abs_strength_corr_pos']:+.2f}); match graph "
            f"density across participants to remove the overall-connectivity-strength confound.")


# ------------------------------------------------------------------ pillar 3 (judgement as numbers)
def _reported_top_set(k=8):
    EXCLUDE = r"absolute|abs\b|_abs|strength|\braw\b|unmatched|fixed|uncorrected"

    def _lists_from(obj, path=""):
        out = []
        if isinstance(obj, dict):
            for kk, vv in obj.items():
                out.extend(_lists_from(vv, path + "/" + str(kk).lower()))
        elif isinstance(obj, list):
            if obj and all(not isinstance(x, (dict, list)) for x in obj):
                out.append((path, obj))
            else:
                for x in obj:
                    out.extend(_lists_from(x, path))
        return out

    candidates = []
    for name in ("ranking.json", "run_metadata.json", "results.json"):
        obj = _load(name)
        if obj is None:
            continue
        for path, lst in _lists_from(obj):
            ids = [pw.canon_id(x) for x in lst if pw.canon_id(x)]
            if len(ids) < 3:
                continue
            excluded = re.search(EXCLUDE, path) is not None
            is_topset = re.search(r"(top|most)[^/]*integrat|top[_ ]?\d|most[_ ]?integ", path) is not None
            is_ordering = re.search(r"rank|order|integrat|most.*least|efficien", path) is not None
            if is_topset and not excluded:
                candidates.append((0, path, ids))
            elif is_ordering and not excluded:
                candidates.append((1, path, ids))
    if candidates:
        candidates.sort(key=lambda t: (t[0], len(t[2])))
        return set(candidates[0][2][:k])
    return None


def test_conclusion_density_matched_not_absolute():
    """The discriminating judgement, graded as numbers. The warranted 'most integrated' ranking
    is the density-matched one; a fixed absolute threshold makes efficiency track overall
    connectivity strength (the confound), giving a near-disjoint ranking. A passing submission
    must EITHER report the density-matched top set (top-k contrast) OR report the
    efficiency<->strength correlation under both conventions with the correct sign split
    (~+0.86 absolute vs ~-0.57 density-matched). And ANY reported confound correlations must
    have the right signs -- a naive single-absolute run cannot produce the density-matched
    (~-0.57) number. (The per-subject proof-of-work in pillars 1-2 is the primary teeth: the
    naive absolute-threshold efficiency fails the density-matched reference match.)"""
    ref = _reference(); st = ref["stats"]
    objs = [_load(n) for n in ("robustness.json", "run_metadata.json", "ranking.json", "results.json")]
    abs_corrs, dm_corrs = pw.collect_confound_corrs(objs)

    dm_top = set(st["DM_TOP"]); abs_top = set(st["ABS_TOP"])
    top = _reported_top_set()
    top_ok = False
    if top:
        dm = len(top & dm_top); ab = len(top & abs_top)
        top_ok = dm >= 2 and dm > ab
    corr_ok = bool(abs_corrs and dm_corrs
                   and max(abs_corrs) >= st["STRENGTH_ABS_MIN"]
                   and min(dm_corrs) <= st["STRENGTH_DM_MAX"])
    assert top_ok or corr_ok, (
        "the submission did not report the density-matched judgement as numbers: neither a "
        "most-integrated set closer to the density-matched ground truth than to the "
        "absolute/strength-confounded one, nor the efficiency<->overall-strength correlation "
        "under both conventions with the correct split (~+0.86 absolute vs ~-0.57 "
        "density-matched). Under a fixed absolute cutoff global efficiency is confounded by "
        "overall connectivity strength; match graph density to compare integration fairly.")

    # any reported confound correlations must carry the correct signs (no fabricated numbers)
    if abs_corrs and dm_corrs:
        assert max(abs_corrs) >= st["STRENGTH_ABS_MIN"], (
            f"reported absolute-threshold efficiency<->strength correlation (max "
            f"{max(abs_corrs):+.2f}) is not strongly positive (>= {st['STRENGTH_ABS_MIN']}); "
            f"on the real data it is ~{st['abs_strength_corr']:+.2f}.")
        assert min(dm_corrs) <= st["STRENGTH_DM_MAX"], (
            f"reported density-matched efficiency<->strength correlation (min "
            f"{min(dm_corrs):+.2f}) is not weak/negative (<= {st['STRENGTH_DM_MAX']}); on the "
            f"real data it is ~{st['dm_strength_corr']:+.2f} once graph density is matched.")


# ------------------------------------------------------------------ secondary prose signal
def test_findings_engage_thresholding_convention():
    """SECONDARY (not the sole gate). findings.md must engage in prose with the thresholding
    convention and the density confound."""
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    conv = re.search(r"proportional|density[- ]?match\w*|absolute (threshold|cutoff|correlation)|"
                     r"fixed (correlation|absolute|density)|graph densit|edge densit", text)
    confound = re.search(r"confound\w*|overall (connectivity )?strength|strongly correlated|"
                         r"driven by|degenerat\w*|convention[- ]?depend\w*|not robust|"
                         r"nearly disjoint|near[- ]?disjoint|density[- ]?depend\w*", text)
    assert conv and confound, (
        "findings.md does not engage in prose with the thresholding convention (absolute vs "
        "density-matched) and the overall-connectivity-strength confound of global efficiency.")
