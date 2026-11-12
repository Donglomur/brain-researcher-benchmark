# Scientific contract companions

These seven source components make the scientific claims of existing benchmark assignments more explicit. They supply descriptive comparisons, reproduction and improvement checks, or links between report claims and evidence. They are additional components of existing tasks; they add no benchmark count, completed experiment, scientific qualification, or submission-readiness claim.

| Component | Scientific purpose | Important boundary |
|---|---|---|
| [ERP neural contribution](neural005/README.md) | Equal-person history-minus-ERP loss, all signed contrasts, and participant sensitivity. | Absolute ERP ranking stays unchanged. Exact full-history matching has no movable cases; no null test or p-value is claimed. |
| [Neuroformer](neuroformer/README.md) | Separate released-code replay, version-specific paper reproduction, and protected improvement. | Full scope and both published Table 1 versions remain; matching declarations do not prove isolation or provenance. |
| [Cerebellar contact decoding](cerebellar/README.md) | Isolate candidate input views and compare matched context and joint predictions. | Retrospective within-session decoding; beating a fixed behavioral reference alone does not establish neural contribution. |
| [Language report claims](language/README.md) | Check numerical claims against complete report support and distinguish external scientific judgments. | Numerical agreement is separate from causal, population, neural-understanding, or meaningful-improvement claims. |
| [Sleep and EOG](sleep/README.md) | Full-cohort paired mode/signal comparisons, numerical claims, and optional probability diagnostics. | Descriptive results require complete admitted support; summary joins do not authenticate raw losses, stochastic replay, or causal effects. |
| [Cerebellar frozen executor](cerebellar_executor/README.md) | A fixed procedure over all 16 sessions and four conditions, with 192 declared phases. | Inactive source; CI inspects source only and runs no Provider, candidate, model, or native process. |
| [Dimensionality and Majaj programme](dimensionality/programme/README.md) | The complete 42-obligation programme, including the released Majaj preparation and analysis branch. | BUILD_ONLY remains enforced and all 24 gates remain open; relocation checks do not run numerical methods or qualify a study. |

Zero, negative, unavailable, and discrepant outcomes remain valid where specified. The components require trusted upstream inputs and operator controls described in their contracts. They do not run trained models or authenticate empirical data merely from supplied metadata. Original task packages and their admission states are unchanged.

The CI checks use invented engineering inputs only. ERP, Neuroformer, language, and sleep use the Python standard library. The cerebellar smoke also uses the exact `numpy==2.4.6` dependency and the small original scorer bundled with its notices. No authentic neural recordings, targets, model weights, paper PDFs, or private review evidence are included.

From a fresh checkout with Python 3.11:

```sh
python -I -S -B benchmarks/scientific_contracts/neural005/test_scientific_contribution.py -v
python -I -S -B -m unittest discover -s benchmarks/scientific_contracts/neuroformer -p test_compare_v2.py
python -B benchmarks/scientific_contracts/language/test_claim_evidence.py
python -I -m pip install --only-binary=:all: --no-deps -r benchmarks/scientific_contracts/cerebellar/requirements.txt
python -I -B benchmarks/scientific_contracts/cerebellar/smoke_contract.py
python -I -S -B benchmarks/scientific_contracts/sleep/test_paired_sleep_contribution.py -v
python -I -S -B benchmarks/scientific_contracts/sleep/test_neural008_numeric_claims.py -v
python -I -S -B benchmarks/scientific_contracts/sleep/test_sleep_claims_integration.py -v
python -I -S -B benchmarks/scientific_contracts/sleep/test_probability_diagnostics_join.py -v
python -I -S -B benchmarks/scientific_contracts/sleep/probability_diagnostics/test_probability_diagnostics.py
python -I -B benchmarks/scientific_contracts/cerebellar_executor/entry.py inspect
python -I -S -B benchmarks/scientific_contracts/dimensionality/programme/test_portability.py
```

The language check creates `language/CONTROL_RESULT_V3.json` exclusively and requires a fresh component copy without that generated file. These commands test implementation and portable imports; they do not execute or qualify a scientific benchmark.

The sleep release preserves its base report and adds a separate [probability summary join](sleep/CALIBRATION_JOIN.md) and [protected-scoring source overlay](sleep/probability_diagnostics/README.md). The base alone continues to report calibration unavailable. The optional join requires the separately admitted probability diagnostics; it does not recover them from confusion counts. The overlay is uninstalled source with invented tests, not a standalone runnable task. Captured fitted-model/source equality does not establish restored stochastic state for shifted comparisons. All original scope, admission, execution and scientific holds remain.

The dimensionality programme retains its full runtime and normative contract scope; the Majaj branch does not replace the larger assignment. Its portable test forbids numerical/cryptographic imports and checks the unchanged BUILD_ONLY refusal before an invocation is read. Cerebellar CI uses only `entry.py inspect`; the separate full inert-graph tests and production `run` route are not invoked here. Both new checks use only the standard library, install no dependencies, and grant no execution authority. Their package documentation retains future dependency, input-rights, runtime and scientific requirements.
