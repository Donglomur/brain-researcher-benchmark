# PAPER-FIND-REP-007 initial evaluator

Executable source-derived stimulus selectivity, pinned-code sequence similarity, reward-predictive activity and reward-zone behavior endpoints for Zhong et al. (2025). Accepts full-session safe NPZ inputs and an explicit longitudinal animal panel; preserves all-cell denominators and reports per-animal changes.

Requires existing Python 3 and NumPy. No installation, download, model fit or native scientific run is performed.

From the repository root:

```bash
python3 benchmarks/paper/PAPER-FIND-REP-007/implementations/initial-evaluator-v1/evaluator.py /path/to/panel.json --output /path/to/report.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s benchmarks/paper/PAPER-FIND-REP-007/implementations/initial-evaluator-v1/tests -v
```

See [input schema, scientific semantics and limitations](../../docs/initial-evaluator-v1.md). `provenance.json` records exact primary-source pins. Native dictionaries can be normalized through the in-memory `normalize_author_imaging` and `normalize_author_behavior` APIs; untrusted pickle is never loaded by this package.

Scientific qualification remains **unknown**. This is a source-construction component, not a whole-paper benchmark or registered score. Authentic full-population replay, protected targets, matching controls, rights/exposure and native parity remain open. The sequence variant follows the pinned source where paper and code disagree. Coding-direction indices and density-map endpoints remain outside this component.
