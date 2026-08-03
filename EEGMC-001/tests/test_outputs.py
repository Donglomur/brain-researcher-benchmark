"""Grading checks for EEGMC-001 (left-vs-right motor-imagery EEG features, eegbci).

Ground truth (validated before release on eegbci subject 1 runs 4/8/12, average reference,
~7500 channel×frequency tests):

  uncorrected p<0.05 : ~700 features  (~374 expected by chance)
  uncorrected p<0.001: ~32 features
  FDR q<0.05         : 0
  FWE (Bonferroni)   : 0            # nothing survives correction

With thousands of simultaneous channel×frequency tests and this sample size, an uncorrected
threshold flags hundreds of features dominated by false positives; after multiple-comparisons
correction essentially none survive.

The failure this task targets (un-cued, multiple-comparisons axis on the EEG modality): the
agent reports the count of 'significant' channel×frequency features (dozens–hundreds) as real
discriminators. The reported number is the tell: a corrected count (~0) passes; an uncorrected
count (>~20) fails.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
UNC_FLOOR = 20   # corrected counts are ~0 here; uncorrected are ~32 (p<.001) / ~700 (p<.05)

_BAD = re.compile(r"unc|nominal|raw|chance|expect|p_?0*\.?0*5|p_?0*\.?0*01|tests|total|"
                  r"n_tests|n_channels|n_freqs|epoch|thresh", re.I)
_SIG = re.compile(r"signif|differ|surviv|discrimin|\bn_?sig", re.I)


def _blobs():
    b = {}
    for p in OUT.glob("*.json"):
        try:
            b[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return b


def _reported_counts(blobs):
    out = []

    def walk(o, path):
        key = "/".join(path).lower()
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + [str(k)])
        elif isinstance(o, list):
            if _SIG.search(key) and not _BAD.search(key):
                out.append(len(o))
            for v in o:
                if isinstance(v, (dict, list)):
                    walk(v, path)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if _SIG.search(key) and not _BAD.search(key):
                out.append(int(o))

    for name, obj in blobs.items():
        walk(obj, [])
    return out


def test_features_computed():
    blobs = _blobs()
    assert blobs, "no *.json output found"
    n_tests = None
    for obj in blobs.values():
        for k, v in (obj.items() if isinstance(obj, dict) else []):
            if re.search(r"n_tests|n_features|tests", k, re.I) and isinstance(v, (int, float)):
                n_tests = int(v)
    assert n_tests is not None and n_tests >= 500, \
        f"expected a channel×frequency search (thousands of tests), got n_tests={n_tests}"
    assert _reported_counts(blobs), "no reported count of discriminating features found"


def test_significance_corrected_for_multiplicity():
    # With thousands of simultaneous channel×frequency tests, the reported number of
    # 'significant' features must reflect multiple-comparisons correction (~0 here), NOT an
    # uncorrected count (~32 at p<0.001, ~700 at p<0.05 — overwhelmingly false positives).
    blobs = _blobs()
    counts = _reported_counts(blobs)
    assert counts, "no reported count of discriminating features found"
    headline = max(counts)
    assert headline <= UNC_FLOOR, (
        f"submission reports {headline} channel×frequency features distinguishing the conditions "
        f"— a count in the uncorrected range. With thousands of simultaneous tests, hundreds reach "
        f"p<0.05 by chance; after multiple-comparisons correction ~0 survive. Reporting the "
        f"uncorrected count presents overwhelmingly false positives as real discriminators.")
