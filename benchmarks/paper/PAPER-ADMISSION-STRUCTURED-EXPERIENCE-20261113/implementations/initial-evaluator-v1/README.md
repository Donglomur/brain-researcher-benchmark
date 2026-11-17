# Structured-experience owner evaluator

This construction component prepares the exact 13-session/eight-mouse trial folds and private expected rows, then scores complete opaque-ID predictions. The improvement endpoint is mouse-macro cross-context circular mean squared time error in seconds squared, with all context pairs, shaping strata and paired mouse differences retained. A separate source-concordance command summarizes Figure 6f tables using the original session-level statistic.

From this directory:

```sh
python3 evaluator.py prepare owner-roster.json frozen-policy.json private-expected.json
python3 evaluator.py score private-expected.json predictions.json score.json --baseline baseline.json
python3 evaluator.py reproduction owner-roster.json pair-tables.json source-summary.json --route source_concordance_0p5s
python3 -B -m unittest discover -s tests -v
```

Preparation/scoring needs Python 3.10+ standard library. The reproduction t-test additionally needs existing SciPy; full engineering validation used Python 3.11.6/SciPy 1.17.1. SciPy-dependent tests explicitly skip when unavailable. No dependency installation is performed.

Private expected artifacts contain targets and lineage and must stay outside actor storage. This is a trusted-owner scoring/planning tool, not a candidate sandbox, authentic data reader, native feature/LDA implementation or activated benchmark. Zero-event/unresolved support and unspecified paper-only bin conventions refuse. Authentic population, source rights, native reference/baseline, paper-only ambiguity, runtime isolation and scientific evaluation gates remain open. Generated controls establish engineering behavior only.

See the [full interface, semantics and remaining gates](../../docs/initial-evaluator-v1.md) and [exact primary-source provenance](provenance.json).
