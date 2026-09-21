"""Proof-of-work grader for N400-001 (ERP CORE N400 semantic word-pair effect at CPz).

The grade is carried by NUMBERS against a held-out reference (`reference.npz`) built by
running the oracle on the ERP CORE N400 recordings (subjects 1-12; CPz; P9/P10 mastoid
reference; 0.1-30 Hz; -200..0 baseline; 300-500 ms mean amplitude):

  PILLAR 1  the submitted per-subject table (per_subject.csv) must cover the exact 12-subject
            sample, be non-constant, and match the held-out per-subject SIGNED target-only
            unrelated-minus-related amplitudes (a negativity). An abs()-ed, sign-flipped, or
            prime+target-pooled table fails.
  PILLAR 2  the mean of the submitted per-subject N400 column must match BOTH the reference
            grand-average AND the reported headline amplitude.
  PILLAR 3  the DISCRIMINATING number is target-only-vs-pooled and is graded IF the agent
            volunteers it (SOCIALBRAIN model): the instruction names only the unrelated-minus-
            related N400 amplitude, so a naive run reports a single number and never volunteers
            the naive prime+target relatedness-pooled amplitude. A submission that reports the
            pooled contrast (found wherever it is reported) must show it ~-4.2 uV, materially
            LESS negative than the target-word contrast (~-8.7 uV, which the pooling halves);
            a run that does not volunteer the pooled number fails.
"""
import json
import os
import re
from pathlib import Path

import numpy as np

import proof_of_work as pw

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF = np.load(Path(__file__).resolve().parent / "reference.npz", allow_pickle=False)

N400_VAL_TOL = 2.5     # per-subject signed N400 amplitude absolute floor (uV)
N400_REL_TOL = 0.20    # ... or within 20% of the reference (wide per-subject spread)
GROUP_TOL = 1.2        # grand-average N400 vs reference / reported (uV)
POOL_TOL = 1.5         # reported pooled amplitude vs reference (uV)
GAP_MIN = 2.0          # target-only must be at least this much MORE NEGATIVE than pooled


def _load(name):
    p = OUT / name
    assert p.exists(), f"missing required output {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _find_number(obj, leaf_re, exclude_re=None):
    """Find a numeric leaf whose (normalised) key matches leaf_re, walking nested dicts/lists.
    Used to grade a volunteered number 'wherever the agent reports it' (SOCIALBRAIN model)."""
    lre = re.compile(leaf_re)
    xre = re.compile(exclude_re) if exclude_re else None
    best = []

    def walk(cur):
        if isinstance(cur, dict):
            for k, v in cur.items():
                nk = _norm(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if lre.search(nk) and not (xre and xre.search(nk)):
                        fv = float(v)
                        if np.isfinite(fv):
                            best.append(fv)
                walk(v)
        elif isinstance(cur, list):
            for v in cur:
                walk(v)

    walk(obj)
    return best[0] if best else None


def _pooled_amplitude():
    """The volunteered naive prime+target relatedness-pooled amplitude, from wherever it is
    reported across the JSON outputs (not a field the instruction names)."""
    for name in ("n400.json", "run_metadata.json"):
        p = OUT / name
        if not p.exists():
            continue
        try:
            blob = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        v = _find_number(blob, r"pool|primeplustarget|primetarget|relatednesspool|allepoch|primeandtarget",
                         exclude_re=r"nsub|count|window|channel|npool")
        if v is not None:
            return v
    return None


def _submitted():
    csvp = OUT / "per_subject.csv"
    assert csvp.exists(), (
        "missing per_subject.csv -- the task requires a per-subject table with each subject's "
        "target-only unrelated-minus-related N400 amplitude")
    return pw.load_submitted(str(csvp), {
        "n400": ["n400_uv", "n400", "target", "unrelated_minus_related", "diff"],
        "pooled": ["pooled"],
    })[0]


# ---- PILLAR 3: target-only-vs-pooled (discriminating number, graded if volunteered) ----
def test_pooled_contrast_is_volunteered_and_numeric():
    data = _load("n400.json")
    amp = _num(data.get("n400_difference_amplitude_uv"))
    pooled = _pooled_amplitude()
    m = float(REF["target_mean"]); pm = float(REF["pooled_mean"])
    assert amp is not None, "n400.json missing n400_difference_amplitude_uv"
    assert amp < 0, f"the N400 difference amplitude must be SIGNED negative; got {amp}"
    assert abs(amp - m) <= GROUP_TOL, (
        f"reported N400 {amp:.2f} uV is not within {GROUP_TOL} of the reference target-word "
        f"grand-average {m:.2f} uV. The prime+target pooled value (~{pm:.2f} uV) halves the "
        f"effect and must not be reported as the headline.")
    assert pooled is not None, (
        "no naive prime+target relatedness-pooled amplitude is reported. The discriminating "
        "judgement graded here is that the unrelated-minus-related N400 must be measured on the "
        "TARGET words; a run that pools prime+target epochs halves the effect. Report the pooled "
        "prime+target amplitude as a number (e.g. a `pooled_prime_plus_target_uv` field) so the "
        "target-locking is quantified.")
    assert abs(pooled - pm) <= POOL_TOL, (
        f"the volunteered prime+target pooled amplitude {pooled:.2f} uV is not the reference "
        f"pooled value (~{pm:.2f} uV).")
    assert amp <= pooled - GAP_MIN, (
        f"the target-word N400 ({amp:.2f} uV) must be materially more negative than the pooled "
        f"value ({pooled:.2f} uV); the gap encodes the prime-dilution")


# ---- PILLAR 1: per-subject signed N400 proof of work -----------------------------------
def test_per_subject_n400_proof_of_work():
    sub = _submitted()
    present = pw.check_subjects_and_values(
        sub, REF["ref_ids"], REF["ref_n400"], "n400", N400_VAL_TOL,
        cover=0.90, match=0.80, eps=1e-2, signed=True, rel_tol=N400_REL_TOL)
    n_neg = sum(sub[i]["n400"] < 0 for i in present)
    assert n_neg >= 0.75 * len(present), \
        f"most subjects should show a negative N400; only {n_neg}/{len(present)} are negative"


# ---- PILLAR 2: recompute the grand-average from the rows -------------------------------
def test_recompute_grandaverage_from_rows():
    sub = _submitted()
    present = [i for i in (pw.canon_id(x) for x in REF["ref_ids"])
               if i in sub and sub[i].get("n400") is not None]
    reported = _num(_load("n400.json").get("n400_difference_amplitude_uv"))
    pw.check_recompute(sub, present, "n400", float(REF["target_mean"]), reported,
                       tol_ref=GROUP_TOL, tol_report=GROUP_TOL)


# ---- SECONDARY: the write-up reports the target-locked effect --------------------------
def test_findings_reports_n400():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert ("n400" in text or "cpz" in text) and ("target" in text or "unrelated" in text), \
        "findings.md does not report the target-word unrelated-minus-related N400 at CPz"
