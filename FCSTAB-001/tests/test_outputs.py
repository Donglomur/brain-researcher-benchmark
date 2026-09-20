"""Proof-of-work grading for FCSTAB-001 (within-run change of the strongest FC edges).

Templates: QSMDIPOLE-001 (held-out reference, tight tolerance) + NETINTEG-001 (grade the
reported result against PINNED real subject ids + a non-constant guard). See
PROOF_OF_WORK_SPEC.md. A passing submission is impossible without running the real
four-selection analysis on the pinned, baked cohort.

Held-out reference (tests/reference.npz), built by running solution/compute.py on the baked
CC200 time series of the exact 40 quality-checked ABIDE cpac subjects (all PITT, eyes closed,
196 TRs / ~4.9 min). Per-subject signed Fisher-z change (second - first) of the top-decile
edges under four selection schemes; group discriminating means:

  forward (top by 1st half)  = -0.212   <- the naive, SELECTION-CONTAMINATED decline
  reverse (top by 2nd half)  = +0.235   <- opposite sign: the "effect" follows the selection
  independent (LOSO strong)  = -0.000   <- selection-free estimate, ~0 (CI [-0.042, +0.042])
  random  (size-matched)     = +0.005   <- selection-free control, ~0

The graded scientific conclusion is NUMERIC, not keyword-based: the naive top-decile decline
cannot by itself establish weakening because selection on the first half biases second-first
downward -- shown by the sign flip under reverse selection and by the selection-free
(independent/random) estimates being ~0 within the prespecified +/-0.05 z equivalence margin.
An agent that only ran the naive forward analysis cannot produce the reverse per-subject
column or the near-zero independent mean, so it fails.

Three pillars (all required):
  1. exact pinned subjects + real per-subject forward/reverse values (kills fabricated/dup rows)
  2. recompute the group means FROM the submitted rows == reported summary == reference
  3. grade the discriminating scheme means as numbers (sign flip + selection-free ~0)
"""
import json
import re

from proof_of_work import (
    OUT, load_reference, load_submitted, resolve_columns, submitted_map, coverage,
    real_id_fraction, nonconstant, per_subject_match, group_mean, reported_scheme_means,
)

REF = load_reference()
ST = REF["stats"]
VAL_TOL = ST["VAL_TOL"]          # per-subject |submitted - ref| for forward/reverse
GROUP_TOL = ST["GROUP_TOL"]      # group-mean recompute vs reference (pinned schemes)
CONSIST = ST["CONSIST_TOL"]      # rows-recompute vs reported-in-summary consistency
NEAR = ST["NEARZERO_MARGIN"]     # |selection-free group mean| upper bound
COVER = ST["COVER"]
MATCH = ST["MATCH"]
EPS = ST["EPS"]


def _summary():
    for name in ("summary.json", "run_metadata.json", "results.json"):
        p = OUT / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _find_numbers(obj, key_re):
    out = []

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if re.search(key_re, key, re.I):
                out.append(float(o))
    walk(obj)
    return out


def _findings():
    p = OUT / "findings.md"
    return p.read_text(encoding="utf-8").lower() if p.exists() else ""


# =============================================================================================
# Pillar 1 -- exact subjects + real per-subject values
# =============================================================================================
def test_csv_covers_exact_pinned_subjects():
    header, rows = load_submitted()
    cols = resolve_columns(header)
    assert cols["id"], f"stability.csv has no subject-id column (columns: {header})"
    idmap = submitted_map(rows, resolve_columns(header)["forward_delta"] or header[-1])
    # need the id column populated; build a bare id set
    ids = {re.sub(r"\D", "", str(r[cols['id']])).lstrip('0') for r in rows if r.get(cols['id'])}
    cov = sum(1 for i in REF["ids"] if i in ids) / len(REF["ids"])
    assert cov >= COVER, (
        f"stability.csv covers only {cov:.0%} of the {len(REF['ids'])} pinned ABIDE subjects "
        f"(need >= {COVER:.0%}); the exact quality-checked cohort must be analysed, not a "
        f"different or fabricated subject list")
    real = sum(1 for i in ids if i in set(REF["ids"])) / max(1, len(ids))
    assert real >= 0.85, (
        f"only {real:.0%} of the submitted subject ids are the real pinned ids -- the table "
        f"appears padded with fabricated subjects")


def test_forward_per_subject_matches_reference():
    """PILLAR 1: the per-subject forward top-decile numbers must be the REAL values for the
    pinned subjects (non-constant, and within tolerance) -- fabricated / constant / duplicated
    rows fail even if the group headline is right."""
    header, rows = load_submitted()
    cols = resolve_columns(header)
    for key, ref_vals in (("forward_first", REF["forward_first"]),
                          ("forward_second", REF["forward_second"]),
                          ("forward_delta", REF["forward_delta"])):
        col = cols[key]
        assert col, f"stability.csv is missing the {key} column (columns: {header})"
        smap = submitted_map(rows, col)
        assert coverage(smap, REF["ids"]) >= COVER, f"{key}: too few pinned subjects present"
        assert nonconstant(smap, EPS), (
            f"{key} is constant across subjects (pstdev <= {EPS}); a real per-subject "
            f"computation is not constant -- looks fabricated/duplicated")
        frac, n = per_subject_match(smap, REF["ids"], ref_vals, VAL_TOL)
        assert frac >= MATCH, (
            f"{key}: only {frac:.0%} of {n} matched subjects are within {VAL_TOL} of the real "
            f"per-subject value (need >= {MATCH:.0%}); the submitted rows are not the real "
            f"first-half-selected top-decile numbers for these subjects")


def test_reverse_per_subject_matches_reference():
    """PILLAR 1 (discriminating): reverse-half selection is not on the naive path. Its
    per-subject signed change must be the REAL values -- an agent that only ran forward
    selection cannot produce this column."""
    header, rows = load_submitted()
    col = resolve_columns(header)["reverse_delta"]
    assert col, (
        "stability.csv has no reverse-half-selection delta column. The task requires the "
        "per-subject signed change of the top-decile edges selected on the SECOND half "
        "(reverse_delta) -- this is what exposes the selection contamination.")
    smap = submitted_map(rows, col)
    assert coverage(smap, REF["ids"]) >= COVER, "reverse_delta: too few pinned subjects present"
    assert nonconstant(smap, EPS), "reverse_delta is constant across subjects -- looks fabricated"
    frac, n = per_subject_match(smap, REF["ids"], REF["reverse_delta"], VAL_TOL)
    assert frac >= MATCH, (
        f"reverse_delta: only {frac:.0%} of {n} matched subjects are within {VAL_TOL} of the "
        f"real reverse-selection value (need >= {MATCH:.0%}). Select the top decile on the "
        f"SECOND half and re-measure the same edges' change; the group mean should be POSITIVE "
        f"(~+0.235), the opposite sign of the forward decline.")


def test_independent_and_random_present_and_nonconstant():
    """The selection-free schemes must actually be computed (present, real spread)."""
    header, rows = load_submitted()
    cols = resolve_columns(header)
    for key in ("independent_delta", "random_delta"):
        col = cols[key]
        assert col, (
            f"stability.csv has no {key} column. The task requires a selection-free strong-edge "
            f"set (independently / LOSO / cross-fitted selected) and a size-matched random "
            f"control, each as a per-subject signed change.")
        smap = submitted_map(rows, col)
        assert coverage(smap, REF["ids"]) >= COVER, f"{key}: too few pinned subjects present"
        assert nonconstant(smap, EPS), f"{key} is constant across subjects -- looks fabricated"


# =============================================================================================
# Pillar 2 -- recompute the group summaries FROM the submitted rows
# =============================================================================================
def test_group_summaries_recompute_from_rows():
    """PILLAR 2: the reported group means must equal what the submitted rows actually produce
    AND the held-out reference. A CSV whose rows don't generate the reported summary fails."""
    header, rows = load_submitted()
    cols = resolve_columns(header)
    summ = _summary()
    reported = reported_scheme_means(summ)

    recompute = {}
    for name, key in (("forward", "forward_delta"), ("reverse", "reverse_delta"),
                      ("independent", "independent_delta"), ("random", "random_delta")):
        col = cols[key]
        assert col, f"cannot recompute: missing {key} column"
        recompute[name] = group_mean(submitted_map(rows, col))

    ref_mean = {"forward": ST["forward_mean"], "reverse": ST["reverse_mean"],
                "random": ST["random_mean"]}
    # (a) rows reproduce the held-out reference for the PINNED schemes
    for name in ("forward", "reverse", "random"):
        assert abs(recompute[name] - ref_mean[name]) <= GROUP_TOL, (
            f"group mean of {name}_delta recomputed from the submitted rows is "
            f"{recompute[name]:+.3f}, not the reference {ref_mean[name]:+.3f} "
            f"(tol {GROUP_TOL}) -- the per-subject rows are not the real analysis")
    # (b) the selection-free means are ~0 (recomputed from rows)
    for name in ("independent", "random"):
        assert abs(recompute[name]) <= NEAR, (
            f"group mean of {name}_delta recomputed from rows is {recompute[name]:+.3f}; the "
            f"selection-free change must be ~0 (|mean| <= {NEAR})")
    # (c) reported summary is CONSISTENT with the rows (no inconsistent hand-written summary)
    assert reported, ("summary.json must report per-scheme delta means under "
                      "selection_schemes.{forward,reverse,independent,random}.delta_mean")
    for name, val in reported.items():
        if name in recompute:
            assert abs(val - recompute[name]) <= CONSIST, (
                f"summary.json reports {name} delta_mean = {val:+.3f} but the submitted rows "
                f"give {recompute[name]:+.3f} (tol {CONSIST}) -- summary inconsistent with the CSV")


# =============================================================================================
# Pillar 3 -- grade the scientific conclusion as NUMBERS
# =============================================================================================
def test_conclusion_numbers_show_selection_contamination():
    """PILLAR 3 (numeric judgement): the discriminating scheme means must jointly establish
    that the naive forward decline is selection-contaminated -- (i) a real forward decline,
    (ii) an opposite-sign reverse effect (the sign follows the selection, not time), and
    (iii) a selection-free (independent) estimate ~0 and far smaller than the naive decline.
    Only an analysis that actually ran all four selections can report these."""
    summ = _summary()
    reported = reported_scheme_means(summ)
    assert {"forward", "reverse", "independent", "random"} <= set(reported), (
        f"summary.json must report all four selection-scheme delta means; got {sorted(reported)}")
    f, r, ind, rnd = (reported["forward"], reported["reverse"],
                      reported["independent"], reported["random"])

    # (i) real forward decline, matching the reference naive contrast
    assert f < -0.10 and abs(f - ST["forward_mean"]) <= GROUP_TOL, (
        f"forward delta_mean {f:+.3f} is not the real naive top-decile decline "
        f"(~{ST['forward_mean']:+.3f})")
    # (ii) reverse selection flips the sign (the "effect" is set by the selected half)
    assert r > 0.10 and (f < 0 < r), (
        f"reverse delta_mean {r:+.3f} does not show the sign flip vs forward {f:+.3f}; selecting "
        f"the strongest edges on the SECOND half must give a positive change of similar "
        f"magnitude -- proof the decline is a selection artefact, not a temporal process")
    assert abs(r - ST["reverse_mean"]) <= 0.06, (
        f"reverse delta_mean {r:+.3f} is far from the reference {ST['reverse_mean']:+.3f}")
    # (iii) the selection-free estimate is ~0 and far below the naive magnitude
    assert abs(ind) <= NEAR, (
        f"independent (selection-free) delta_mean {ind:+.3f} is not ~0 (|mean| <= {NEAR}); the "
        f"LOSO/independently-selected strong-edge change is the genuine early-to-late estimate")
    assert abs(ind) < 0.5 * abs(f), (
        f"independent delta_mean {ind:+.3f} is not markedly smaller than the naive forward "
        f"decline {f:+.3f}; the selection-free change must be far closer to zero")
    assert abs(rnd) <= NEAR, f"random-control delta_mean {rnd:+.3f} is not ~0 (|mean| <= {NEAR})"


# --- v2 negation-aware prose guard (SECONDARY: the numbers above carry the grade) -----------
_NEG = (r"(?:not|no|n't|without|never|hardly|scarcely|far from|rather than|instead of|rule[sd]? out|"
        r"ruled out|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|fails? to|"
        r"unable to|unlikely to|does not|do not)")


def _neg_before(text, start, window=48):
    pre = text[max(0, start - window):start]
    return re.search(r"(?<![a-z])" + _NEG + r"(?![a-z])[\s\w,'\"()-]{0,20}$", pre, re.I) is not None


def _unnegated(text, pat, window=48):
    for m in re.finditer(pat, text, re.I):
        if _neg_before(text, m.start(), window):
            continue
        if re.search(r"\b" + _NEG + r"\b", m.group(0), re.I):
            continue
        return True
    return False


def test_findings_conclusion_not_genuine_weakening():
    """SECONDARY prose guard (must not be the sole gate): findings.md must state the
    selection-contamination reading and must NOT, un-negated, conclude a genuine within-run
    weakening of the strongest connections."""
    text = _findings()
    assert text, "findings.md is missing or empty"

    contamination = (
        r"selection[-\s]?(?:contaminat|bias|effect|driven|artefact|artifact)"
        r"|contaminated\s+by\s+select|biased\s+(?:down|downward|by\s+select)"
        r"|cannot\s+(?:by\s+itself\s+)?establish|does\s+not\s+establish|not\s+establish\w*"
        r"|regress\w*\s+to(?:wards?)?\s+(?:the\s+)?mean|reversion\s+to(?:wards?)?\s+(?:the\s+)?mean"
        r"|opposite\s+sign|sign\s+(?:flip|revers|change)|flip\w*\s+(?:the\s+)?sign"
        r"|select\w*\s+on\s+the\s+(?:second|other)\s+half"
        r"|independent\w*\s+(?:select|set|strong|estimate)|loso|cross[-\s]?fit"
        r"|selection[-\s]free|not\s+(?:a\s+)?(?:real|genuine|true)\s+(?:within-?run\s+)?"
        r"(?:weakening|decline|change|effect)"
    )
    assert re.search(contamination, text, re.I), (
        "findings.md does not state the selection-contamination reading (that the naive "
        "top-decile decline cannot by itself establish weakening -- shown by the reverse-half "
        "sign flip and the selection-free/independent estimate being ~0).")

    genuine = (
        r"(?:so|therefore|thus|hence|conclude\w*|we\s+(?:find|conclude|show))"
        r"[^.\n]{0,80}(?:genuine\w*|real|true|truly|actually)\s+(?:within-?run\s+)?"
        r"(?:weaken\w*|declin\w*|decreas\w*)"
        r"|is\s+a\s+(?:genuine|real|true)\s+within-?run\s+(?:decline|weakening|decrease)"
        r"|connections?\s+(?:genuinely|really|truly)\s+weaken"
        r"|strongest\s+connections?\s+(?:genuinely|really|truly|do)\s+weaken"
    )
    assert not _unnegated(text, genuine), (
        "findings.md concludes a GENUINE within-run weakening of the strongest connections. "
        "The naive top-decile decline is selection-contaminated (the sign flips under "
        "reverse-half selection and the selection-free estimate is ~0); it cannot by itself "
        "establish weakening.")
