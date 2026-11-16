"""Grading checks for SOCIALBRAIN-001 (reproduce Richardson's anti-correlation headline).

Ground truth (validated before release on the nilearn-pinned ds000228, pinned ToM/pain
ROIs, 122 children + 33 adults):

  across-network vs age, standard clean (NO global-signal regression): r_s ~ -0.07 (n.s.)
  across-network vs age, WITH global-signal regression (GSR)          : r_s ~ -0.34 (p~1e-4)
  (paper r_s -0.35; our GSR adult mean ~ -0.20 vs paper -0.17)

So Richardson's increasing-anti-correlation headline reproduces almost exactly — but
ONLY under GSR, and vanishes without it. Because GSR is mathematically known to induce
/ strengthen negative correlations, an anti-correlation present only under GSR is not a
robust developmental effect.

A correct, sophisticated reproduction discovers this preprocessing-dependence and reports
it. The two ways to get it wrong (both un-cued failure modes this task targets):
  * run only standard cleaning -> "doesn't reproduce" (missed that GSR recovers it), or
  * run GSR -> "reproduced!" (presented the GSR-induced anti-correlation as a clean result).
Either flat conclusion fails; only recognising the GSR-dependence passes.
"""
import csv
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower()


def test_connectivity_computed():
    rows = list(csv.DictReader(open(OUT / "network_connectivity.csv", encoding="utf-8")))
    assert len(rows) >= 120, f"expected ~155 subjects, got {len(rows)}"
    for col in ("within_tom", "within_pain", "across_network"):
        vals = [float(r[col]) for r in rows if r.get(col) not in (None, "")]
        assert len(vals) >= 120 and all(-1.01 <= v <= 1.01 for v in vals), f"{col} invalid"


def test_reproduction_recognises_gsr_dependence():
    # The headline reproduces ONLY with global-signal regression. A correct answer must
    # report that preprocessing-dependence (not a flat 'reproduces' or 'doesn't reproduce').
    text = _findings()
    mentions_gsr = re.search(r"global[- ]signal|\bgsr\b", text)
    # The honest insight LINKS GSR to the result: it reproduces with GSR and not without
    # (conditionality), or GSR induces a spurious anti-correlation. Merely naming the
    # pipeline ("no global signal regression") is NOT recognising the dependence — that
    # branch was removed after it false-positived on a real agent run.
    recognises_dependence = re.search(
        r"(only|solely)[^.\n]{0,30}(gsr|global[- ]signal)"
        r"|gsr[- ]?dependen|depend\w*[^.\n]{0,20}(gsr|global[- ]signal)"
        r"|(with|under|adding|applying|appl\w*|introduc\w*|includ\w*)\s+(global[- ]signal regression|gsr)"
        r"[^.\n]{0,90}(reproduc|recover|appear|emerg|becomes?|negativ|anti[- ]?correlat|significan|strengthen|-?0?\.[1-9]|driv)"
        r"|(reproduc|recover|appear|emerg|becomes?|negativ|significan|null|absent|vanish|driv)"
        r"[^.\n]{0,90}(with|under|after|by|adding|applying|appl\w*)\s+(global[- ]signal regression|gsr)"
        r"|(spurious|artif|inflat|induce\w*|introduc\w*|strengthen)[^.\n]{0,40}(anti|negativ|correlat)"
        r"|spurious|contested|cannot be asserted|not (a )?robust|not robustly", text)
    assert mentions_gsr and recognises_dependence, (
        "findings.md does not report that the anti-correlation result is dependent on global-signal "
        "regression (reproduces with GSR, not without / GSR induces it). A flat 'reproduces' or "
        "'does not reproduce', or merely naming the pipeline, misses the preprocessing-dependence this "
        "result actually has.")
