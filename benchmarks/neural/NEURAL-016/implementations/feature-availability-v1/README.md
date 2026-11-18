# Feature availability at the prediction time

NEURAL-016 forbids future-valued predictors. Its existing protocol validates
nominal lags and response windows, but a lag of zero does not establish when a
feature becomes available. The original annotations include whole-word audio
summaries and pre/post-onset differences; using their names at zero lag can hide
future input. These definitions are described in the
[source paper, Appendix A.2 and Table 4](https://arxiv.org/html/2411.08343v1).

This operator entrypoint requires a separately frozen feature manifest before it
calls the existing bound-nuisance scorer. Each feature has a conservative input
support interval and an availability offset relative to its anchor. For **every**
declared lag, availability plus lag must be no later than the row time. The
declared guard and continuous block must cover the complete shifted input
support. Computation latency can make availability later than the last input.
Features available before their last required input are rejected.

This preserves the existing targets, nuisance comparator, signed delta R²,
weighting, uncertainty and source holds. It does not silently relabel the
original features as causal, change their computation, or execute a model.
The independently supplied file digest binds declarations; extractor conformance,
actual provenance, protected execution and scientific qualification remain open.
Passing this check does not establish native or viewer interpretation.

The manifest has exactly these top-level fields:

```json
{
  "schema_version": 1,
  "task_id": "NEURAL-016",
  "protocol_sha256": "operator-computed canonical protocol digest",
  "policy": "available_at_row_time",
  "coverage": "all_declared_fit_and_evaluation_rows",
  "features": []
}
```

Each feature item has `name`, `role`, `support_seconds: [earliest, latest]`,
`available_after_seconds`, `definition`, and `extractor_sha256`. Names and roles
must exactly cover the frozen nuisance and linguistic feature lists. Offsets
are seconds from the **feature anchor**, then shifted by each protocol lag.
For variable-duration features, the declared interval must conservatively
cover every fitting and evaluation row; unknown bounds must not be guessed.
`extractor_sha256` identifies the operator's specified extractor artifact; this
entrypoint does not read or authenticate that artifact. Free-text definitions
are operator metadata and must not be exposed as a participant answer channel.

For example, a feature requiring input through 0.5 s after its anchor cannot
pass at zero lag. If the frozen scientific protocol permits its anchor at
−0.5 s, and it is available immediately after that input, its latest availability
is exactly the row time. That is a different explicitly frozen lag choice,
not permission to modify the source recipe after inspecting outcomes.

Use the predecessor's CLI arguments plus
`--operator-feature-manifest PATH` and
`--expected-feature-manifest-sha256 OPERATOR_CONFIGURED_DIGEST`.
The expected digest must come from independent operator configuration, never
from candidate-supplied data. Invalid support is rejected before nuisance,
candidate or private-target reads. Comparator replacement is still rejected
before private targets. Scores replace the destination atomically only after
successful evaluation. This CLI is not a filesystem sandbox.

The focused generated controls in `test_evaluator.py` cover effective support,
latency, the whole-word/post-onset trap, lagged availability, guard coverage,
complete feature identity, fixed byte/protocol binding, retained scores and
rejection before private inputs. They contain no authentic signals or fits.
The component is additive and requires explicit enrollment by the repository
integrator; neither a canonical contract nor readiness is changed here.
