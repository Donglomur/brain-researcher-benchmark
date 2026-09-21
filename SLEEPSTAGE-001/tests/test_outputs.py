"""Proof-of-work grader for SLEEPSTAGE-001 (5-class AASM sleep staging on Sleep-EDF).

The grade is carried by NUMBERS against a held-out reference (`reference.npz`) built by
running the oracle on the pinned Sleep-EDF set (subjects [0..5], night 1; EEG Fpz-Cz +
Pz-Oz; 30-s epochs; relative band-power features; RandomForest(200, random_state=0)):

  PILLAR 1  the submitted per-subject table (per_subject.csv) must cover the exact 6-subject
            leave-one-subject-out sample, be non-constant, and match the held-out per-subject
            LOSO accuracy and Cohen kappa.
  PILLAR 2  the epoch-weighted accuracy recomputed FROM the submitted rows must match BOTH the
            reference subject-wise accuracy AND the reported headline accuracy.
  PILLAR 3  the DISCRIMINATING number is LOSO-vs-random and is graded IF the agent volunteers it
            (SOCIALBRAIN model): the instruction names only the cross-validated accuracy, so a
            naive run reports one number and never volunteers the leaky random epoch-wise k-fold
            accuracy. The reported headline accuracy must be the subject-wise accuracy (which
            pillars 1-2 already pin), and the volunteered random-kfold accuracy (found wherever it
            is reported) must be materially ABOVE it. A run that does not volunteer the leaky
            random-kfold number fails.

Consecutive 30-s epochs from one night are autocorrelated and share subject identity, so a
random epoch-wise k-fold leaks and inflates the estimate; the subject-wise figure is honest.
"""
import json
import os
import re
from pathlib import Path

import numpy as np

import proof_of_work as pw

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF = np.load(Path(__file__).resolve().parent / "reference.npz", allow_pickle=False)

ACC_VAL_TOL = 0.06     # per-subject LOSO accuracy
KAPPA_VAL_TOL = 0.08   # per-subject LOSO kappa
GROUP_TOL = 0.035      # group accuracy/kappa vs reference / reported
RAND_TOL = 0.05        # reported random-kfold accuracy vs reference
GAP_MIN = 0.04         # subject-wise must be at least this far BELOW random-kfold


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
    Grades a number 'wherever the agent reports it' (SOCIALBRAIN model)."""
    lre = re.compile(leaf_re)
    xre = re.compile(exclude_re) if exclude_re else None
    hits = []

    def walk(cur):
        if isinstance(cur, dict):
            for k, v in cur.items():
                nk = _norm(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if lre.search(nk) and not (xre and xre.search(nk)):
                        fv = float(v)
                        if np.isfinite(fv):
                            hits.append(fv)
                walk(v)
        elif isinstance(cur, list):
            for v in cur:
                walk(v)

    walk(obj)
    return hits[0] if hits else None


def _random_kfold(metric):
    """The volunteered leaky random epoch-wise k-fold accuracy/kappa, from wherever it is
    reported across the JSON outputs (not a field the instruction names). metric in {acc, kappa}."""
    leaf = (r"random|kfold|epochwise|leaky") if metric == "acc" else r"random|kfold|epochwise|leaky"
    need = r"acc" if metric == "acc" else r"kappa|cohen"
    for name in ("staging_results.json", "run_metadata.json"):
        p = OUT / name
        if not p.exists():
            continue
        try:
            blob = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        v = _find_number(blob, rf"(?=.*(?:{leaf}))(?=.*(?:{need}))",
                         exclude_re=r"nsub|count|nepoch|nfold|fold$|scheme")
        if v is not None:
            return v
    return None


def _submitted():
    csvp = OUT / "per_subject.csv"
    assert csvp.exists(), (
        "missing per_subject.csv -- the task requires a per-subject table with each held-out "
        "subject's leave-one-subject-out accuracy and Cohen kappa")
    return pw.load_submitted(str(csvp), {
        "acc": ["accuracy", "acc"],
        "kappa": ["kappa", "cohen"],
        "neps": ["n_test_epochs", "n_epochs", "epochs"],
    })[0]


# ---- PILLAR 3: LOSO-vs-random discriminating number (graded if volunteered) ------------
def test_random_kfold_leakage_is_volunteered_and_numeric():
    data = _load("staging_results.json")
    assert int(data.get("n_classes", len(data.get("classes", [])))) == 5, \
        "must be a five-class staging problem"
    headline = _num(data.get("accuracy"))
    kappa = _num(data.get("cohen_kappa"))
    rand = _random_kfold("acc")
    s_acc = float(REF["subj_acc"]); s_k = float(REF["subj_kappa"]); r_acc = float(REF["rand_acc"])
    assert headline is not None and abs(headline - s_acc) <= GROUP_TOL, (
        f"reported headline accuracy {headline} is not the subject-wise accuracy "
        f"({s_acc:.3f} +/- {GROUP_TOL}). Reporting the leaky random-kfold accuracy "
        f"(~{r_acc:.3f}) as the headline over-claims generalisation.")
    assert kappa is not None and abs(kappa - s_k) <= GROUP_TOL, \
        f"reported cohen_kappa {kappa} is not the subject-wise kappa {s_k:.3f} +/- {GROUP_TOL}"
    assert rand is not None, (
        "no leaky random epoch-wise k-fold accuracy is reported. The discriminating judgement "
        "graded here is that consecutive 30-s epochs from one night are autocorrelated and share "
        "subject identity, so a random epoch-wise k-fold leaks and inflates the estimate; the "
        "honest figure holds out whole subjects. Report the random-kfold accuracy as a number "
        "(e.g. a `random_kfold_accuracy` field) so the leakage is quantified.")
    assert abs(rand - r_acc) <= RAND_TOL, (
        f"volunteered random-kfold accuracy {rand} is not the reference random-kfold accuracy "
        f"{r_acc:.3f} +/- {RAND_TOL}")
    assert headline <= rand - GAP_MIN, (
        f"the subject-wise accuracy ({headline:.3f}) must be materially below the random-kfold "
        f"accuracy ({rand:.3f}); the gap encodes the epoch-wise leakage")


# ---- PILLAR 1: per-subject accuracy + kappa proof of work ------------------------------
def test_per_subject_accuracy_proof_of_work():
    sub = _submitted()
    pw.check_subjects_and_values(
        sub, REF["ref_ids"], REF["ref_acc"], "acc", ACC_VAL_TOL,
        cover=0.90, match=0.80, eps=1e-3, signed=True)


def test_per_subject_kappa_proof_of_work():
    sub = _submitted()
    pw.check_subjects_and_values(
        sub, REF["ref_ids"], REF["ref_kappa"], "kappa", KAPPA_VAL_TOL,
        cover=0.90, match=0.80, eps=1e-3, signed=True)


# ---- PILLAR 2: recompute the group accuracy from the rows -------------------------------
def test_recompute_accuracy_from_rows():
    sub = _submitted()
    present = [i for i in (pw.canon_id(x) for x in REF["ref_ids"])
               if i in sub and sub[i].get("acc") is not None and sub[i].get("neps") is not None]
    assert len(present) >= 0.9 * len(REF["ref_ids"]), \
        "per_subject.csv must include n_test_epochs to recompute the epoch-weighted accuracy"
    reported = _num(_load("staging_results.json").get("accuracy"))
    pw.check_recompute(sub, present, "acc", float(REF["subj_acc"]), reported,
                       tol_ref=GROUP_TOL, tol_report=GROUP_TOL, weight_key="neps")


# ---- SECONDARY: the write-up volunteers the leakage rationale ---------------------------
def test_findings_reports_leakage():
    text = re.sub(r"\s+", " ", (OUT / "findings.md").read_text(encoding="utf-8").lower())
    assert ("subject" in text and ("leak" in text or "random" in text or "k-fold" in text
                                   or "kfold" in text or "generalis" in text or "generaliz" in text)), \
        "findings.md does not volunteer the subject-wise vs random-kfold leakage rationale"
