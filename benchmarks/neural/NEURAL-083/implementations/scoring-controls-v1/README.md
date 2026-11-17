# Full-panel scoring controls

This adds generated numerical controls for the existing NEURAL-083 scorer and
three-panel paired report. The existing task-local portability checks capture
those modules but do not exercise their scientific metric calculations. No
production estimator, scorer, preparation path, task definition, or historical
evidence is changed here.

`test_scoring.py` captures three exact task-local source files and checks their
SHA256 identities before execution. It restores the predecessor's temporary
`protocol` import and search-path changes. The tests use only the Python
standard library and generated binary labels/probabilities; they never open
authentic recordings, historical answers, or predictions, and never fit a model.

The controls retain the complete 54-person, two-session, 100-query geometry and
all four settings × three arms (1,296 condition outputs per panel). Known counts
of correct predictions in each class independently determine expected metrics:

- Every person's two-session mean, the complete person macro average, and all
  five paired calibration/representation contrasts, including descriptive SE.
- Probability 0.5 predicting right, including a mixed left=0.2/right=0.5
  case that distinguishes `>= 0.5` from `> 0.5`, exact 0/1 probabilities,
  and the 1e-15 log-loss floor.
- Identity joins independent of whole-case/outcome ordering, while reordered
  query predictions are rejected.
- Missing/duplicate conditions, generation mismatch, Boolean/nonfinite/out-of-
  range probabilities, wrong protected identities, and wrong class support.
- Whole-panel abstention and malformed-output rejection before protected target
  access; all three comparison panels are validated even if the first abstains.
- Adaptive-minus-frozen balanced accuracy, frozen-minus-adaptive log loss, and
  the EEG-minus-context interaction, with a single external target callback.

The selected source identities are:

| Task-local source under `implementations/case-adaptive` | SHA256 |
| --- | --- |
| `bindings/scoring_sources/protocol.py` | `90898be76b4193e7b26e2765b2ab80b040bb519c91245ac09c252e92e4de7699` |
| `bindings/scoring_sources/scorer_core.py` | `31a37f8df65dd0d760cf42cb7575914b97a5ec7207354822e789107e00ca7483` |
| `successor/paired_report.py` | `e3482c46fe9ac274e7725d79bd5df0498bbf6f244f6320251f874be2d06612d0` |

The source protocol cites [OpenBMI](https://github.com/PatternRecognition/OpenBMI)
revision `c0e56825366681ae576801af08eb5fe326a5afd8` and the
[collection paper](https://doi.org/10.1093/gigascience/giz002). This control suite
validates the registered prospective probability endpoint, which is distinct
from the source paper's native per-session CSP/LDA accuracy analysis.

Run `python3 -I -S -B test_scoring.py` from this directory, using the shared
bounded test pool when the parallel-build policy applies. No dependencies need
installation. A changed source pin requires review of the selected source and
the test expectations; do not update pins just to suppress a failure.

Passing these controls establishes generated software behavior only. The full
108-recording acquisition/schema binding, authentic numerical preparation,
independent reference competence, execution isolation, paired model conditions,
and direct/viewer delivery remain unqualified. These controls establish no
new model performance, physiological intention decoding, scientific improvement,
population confidence interval, or completed benchmark.
