"""Proof-of-work grader for EYESTATE-001 — reproduce the ABIDE eyes-open-vs-closed
cross-validated balanced accuracy, and report the site-blocked vs random-fold discrepancy.

EYESTATE reports one headline number, so the previous verifier (range + keyword) could be
passed by writing any in-band value. This grader validates the PER-FOLD (per-held-out-site)
balanced accuracies against a held-out reference (tests/reference.npz, built from the oracle
run with the pinned stack), recomputes the headline FROM those per-fold rows, and grades the
scientific judgement AS NUMBERS: the honest site-blocked (leave-one-site-out) accuracy is well
below the leaky random-fold accuracy, because eye status is aligned with acquisition site and
connectivity carries a site fingerprint. Keyword prose is only secondary.

Reference (ABIDE cpac filt_noglobal rois_cc200, N=1035, 20 sites, LinearSVC C=1):
  leave-one-site-out (site-blocked, CORRECT) balanced accuracy ~ 0.737
  random 10-fold (LEAKY)                      balanced accuracy ~ 0.876   (chance 0.5)
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


def _reference():
    assert REF_PATH.exists(), "held-out reference tests/reference.npz is missing"
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "per_fold.csv"
    assert p.exists(), (
        "missing required per-fold output per_fold.csv (one row per cross-validation fold: "
        "fold_site, n_test, balanced_accuracy)")
    return pw.load_submitted(p)


def _results():
    p = OUT / "eye_decoding_results.json"
    assert p.exists(), "missing required output eye_decoding_results.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"eye_decoding_results.json is not valid JSON: {e}")


def _findings():
    return re.sub(r"\s+", " ", (OUT / "findings.md").read_text(encoding="utf-8").lower())


_BACC = r"balancedaccuracy|balancedacc|^bacc$|balacc|^cvbalancedaccuracy$|accuracy"


def _site_blocked(j):
    return pw.find_number(j, leaf_re=r"siteblocked|leaveonesiteout|^loso|siteblockedbalancedaccuracy",
                          path_exclude=["random", "kfold", "leaky", "chance"]) or \
        pw.find_number(j, leaf_re=r"cvbalancedaccuracy|cvbacc|cvaccuracy",
                       path_exclude=["random", "kfold", "leaky"])


def _random(j):
    return pw.find_number(j, leaf_re=r"random|kfold|leaky",
                          path_include=[], path_exclude=["chance", "nsites", "nsubjects"],
                          prefer=["randomkfold", "kfold", "random", "leaky"])


def _headline(j):
    return pw.find_number(j, leaf_re=r"cvbalancedaccuracy|cvbacc|cvaccuracy",
                          path_exclude=["random", "kfold", "leaky"]) or _site_blocked(j)


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    sub = _submitted()
    assert len(sub) >= 6, f"per_fold.csv must carry per-fold accuracies; parsed {len(sub)} folds"
    assert all(0.0 <= v <= 1.0 for v in sub.values()), "balanced accuracies out of [0,1]"
    j = _results()
    assert isinstance(j, dict) and j, "eye_decoding_results.json empty"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_folds_and_values():
    ref = _reference(); sub = _submitted(); st = ref["stats"]
    pw.check_folds_and_values(sub, ref, val_tol=st["VAL_TOL"], corr_min=st["CORR_MIN"],
                              cover=st["COVER"], match=st["MATCH"], eps=st["EPS"])


# ------------------------------------------------------------------ pillar 2
def test_recompute_headline_from_folds():
    ref = _reference(); sub = _submitted(); st = ref["stats"]; j = _results()
    import numpy as np
    matched = [i for i in ref["ids"] if i in sub]
    mean_bacc = float(np.mean([sub[i] for i in matched]))
    assert abs(mean_bacc - st["loso_bacc"]) <= st["RECOMP_TOL"] + 0.02, (
        f"mean of the submitted per-fold balanced accuracies ({mean_bacc:.3f}) does not match the "
        f"reference site-blocked accuracy ({st['loso_bacc']:.3f}); the per-fold rows are not real.")
    headline = _headline(j)
    assert headline is not None, "eye_decoding_results.json has no cv_balanced_accuracy headline"
    assert abs(mean_bacc - headline) <= st["RECOMP_TOL"] + 0.02, (
        f"the reported headline balanced accuracy ({headline:.3f}) is not the mean of the submitted "
        f"per-fold rows ({mean_bacc:.3f}); the table and the reported number disagree.")


# ------------------------------------------------------------------ pillar 3 (judgement as numbers)
def test_conclusion_site_blocked_below_random_numeric():
    ref = _reference(); st = ref["stats"]; j = _results()
    site = _site_blocked(j)
    rand = _random(j)
    assert site is not None, (
        "eye_decoding_results.json does not report a site-blocked (leave-one-site-out) balanced "
        "accuracy -- the honest, transferable estimate you must report as the headline.")
    assert rand is not None, (
        "eye_decoding_results.json does not report the random-fold balanced accuracy. The judgement "
        "graded here is that a random-fold split inflates the accuracy via site-fingerprint leakage; "
        "report both the site-blocked and the random-fold numbers.")

    # (a) the reported site-blocked accuracy is the honest ~0.74 (well below the leaky one).
    assert abs(site - st["loso_bacc"]) <= st["LOSO_TOL"], (
        f"reported site-blocked balanced accuracy = {site:.3f} does not match the reference "
        f"({st['loso_bacc']:.3f}, tol {st['LOSO_TOL']}).")
    assert site <= st["LOSO_MAX"], (
        f"reported site-blocked accuracy = {site:.3f} is not below the leaky random-fold level; the "
        f"honest cross-site accuracy is ~{st['loso_bacc']:.2f}.")

    # (b) the random-fold accuracy is markedly higher (site-fingerprint leakage inflation).
    assert abs(rand - st["random_bacc"]) <= st["RAND_TOL"] + 0.02, (
        f"reported random-fold balanced accuracy = {rand:.3f} does not match the reference "
        f"({st['random_bacc']:.3f}); it should be the inflated leaky estimate.")
    assert rand - site >= st["GAP_MIN"], (
        f"the random-fold accuracy ({rand:.3f}) does not exceed the site-blocked accuracy "
        f"({site:.3f}) by the leakage margin; the whole point is that random folds inflate the "
        f"estimate because eye status is aligned with site.")

    # (c) the reported HEADLINE is the site-blocked (honest) number, not the leaky one.
    headline = _headline(j)
    assert headline is not None and abs(headline - site) <= 0.03, (
        f"the reported headline ({headline}) is not the honest site-blocked accuracy ({site:.3f}); "
        f"the leaky random-fold number must not be reported as the result.")


# ------------------------------------------------------------------ secondary prose signal
def test_findings_engage_site_leakage_and_avoid_overclaim():
    """SECONDARY (numbers carry the grade). findings.md must report that the random-fold accuracy
    is inflated by site-fingerprint leakage (eye status aligned with acquisition site) and that
    the site-blocked estimate is the honest one, not report the ~0.87 leaky number as the result."""
    text = _findings()
    SITE = r"(?:site|acquisition|scanner|protocol|batch)"
    LEAK = r"(?:leak\w*|inflat\w*|fingerprint|confound\w*|overstate\w*|optimist\w*|aligned|identif\w*|" \
           r"generali[sz]|transfer\w*)"
    BLOCK = r"(?:leave-?one-?site-?out|site-?blocked|blocked by site|per-?site|cross-?site|" \
            r"grouped? by site|held-?out site)"
    engages = re.search(rf"{SITE}[^.\n]{{0,80}}{LEAK}", text) and \
        (re.search(BLOCK, text) or re.search(rf"{LEAK}[^.\n]{{0,80}}{SITE}", text))
    assert engages, (
        "findings.md does not report that random-fold cross-validation inflates the accuracy via "
        "site-fingerprint leakage and that a site-blocked (leave-one-site-out) evaluation is the "
        "honest estimate.")

    # over-claim guard: must not present the leaky ~0.87 as the genuine eyes-open/closed accuracy.
    overclaim = re.search(
        r"(?:balanced accuracy|accuracy)\s+of\s+0?\.8[5-9][^.\n]{0,40}"
        r"(?:genuine|robust|real|true|transferable|generali[sz]|eyes)"
        r"|0?\.8[5-9][^.\n]{0,30}is\s+the\s+(?:accuracy|estimate)\s+(?:i|we)\s+report", text)
    assert not overclaim, (
        "findings.md reports the leaky random-fold accuracy (~0.87) as the genuine decoding "
        "accuracy; the honest, site-blocked estimate (~0.74) is what should be reported.")
