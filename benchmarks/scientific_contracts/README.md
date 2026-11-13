# Scientific contract companions

These eleven source components make the scientific claims of existing benchmark assignments more explicit. They supply descriptive comparisons, reproduction and improvement checks, or links between report claims and evidence. They are additional components of existing tasks; they add no benchmark count, completed experiment, scientific qualification, or submission-readiness claim.

| Component | Scientific purpose | Important boundary |
|---|---|---|
| [ERP neural contribution](neural005/README.md) | Equal-person history-minus-ERP loss, all signed contrasts, and participant sensitivity. | Absolute ERP ranking stays unchanged. Exact full-history matching has no movable cases; no null test or p-value is claimed. |
| [Neuroformer](neuroformer/README.md) | Separate released-code replay, version-specific paper reproduction, and protected improvement. | Full scope and both published Table 1 versions remain; matching declarations do not prove isolation or provenance. |
| [Cerebellar contact decoding](cerebellar/README.md) | Isolate candidate input views and compare matched context and joint predictions. | Retrospective within-session decoding; beating a fixed behavioral reference alone does not establish neural contribution. |
| [Language report claims](language/README.md) | Check numerical claims against complete report support and distinguish external scientific judgments. | Numerical agreement is separate from causal, population, neural-understanding, or meaningful-improvement claims. |
| [Sleep and EOG](sleep/README.md) | Full-cohort paired mode/signal comparisons, numerical claims, and optional probability diagnostics. | Descriptive results require complete admitted support; summary joins do not authenticate raw losses, stochastic replay, or causal effects. |
| [Cerebellar frozen executor](cerebellar_executor/README.md) | A fixed procedure over all 16 sessions and four conditions, with 192 declared phases. | Inactive source; CI inspects source only and runs no Provider, candidate, model, or native process. |
| [Dimensionality and Majaj programme](dimensionality/programme/README.md) | The complete 42-obligation programme, including the released Majaj preparation and analysis branch. | BUILD_ONLY remains enforced and all 24 gates remain open; relocation checks do not run numerical methods or qualify a study. |
| [OpenBMI paired case-adaptive source](openbmi_case_adaptive/README.md) | Compare a frozen programme and per-condition investigation across the complete 54-person, two-session assignment. | Inactive source with missing external admissions; strategy differences do not isolate model treatment, neural contribution or equal realized compute. |
| [FIND-025 submission and comparison](find025/README.md) | Preserve both paper claim families and all 16 obligation groups while validating declarations and retaining missing or failed outcomes. | Reconstruction, held paper reproduction and protected improvement remain separate; consistent declarations do not prove authentic results. |
| [NEURAL-094 regional comparison](neural094/README.md) | Complete frozen-program, investigator-policy and reference comparison across 39 sessions, ten mice, 73 regions, 2,628 pairs and five seeds. | Inactive source; whole-population primary and all native, input, provider, rights and scientific gates remain. |
| [NEURAL-035 closed paired grading](neural035/README.md) | Complete fixed-program and public-rank comparison across 14 sessions, seven mice, 1,012 cells, 28 queries per role and 99 shifts. | Inactive source; protected metadata, authentic process authority, inputs, native and scientific qualifications remain external. |

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
python3 -I -S -B benchmarks/scientific_contracts/openbmi_case_adaptive/test_portability.py
python3.11 -I -S -B -m unittest discover -s benchmarks/scientific_contracts/find025 -p test_find025_contract.py
```

The language check creates `language/CONTROL_RESULT_V3.json` exclusively and requires a fresh component copy without that generated file. These commands test implementation and portable imports; they do not execute or qualify a scientific benchmark.

The sleep release preserves its base report and adds a separate [probability summary join](sleep/CALIBRATION_JOIN.md) and [protected-scoring source overlay](sleep/probability_diagnostics/README.md). The base alone continues to report calibration unavailable. The optional join requires the separately admitted probability diagnostics; it does not recover them from confusion counts. The overlay is uninstalled source with invented tests, not a standalone runnable task. Captured fitted-model/source equality does not establish restored stochastic state for shifted comparisons. All original scope, admission, execution and scientific holds remain.

The dimensionality programme retains its full runtime and normative contract scope; the Majaj branch does not replace the larger assignment. Its portable test forbids numerical/cryptographic imports and checks the unchanged BUILD_ONLY refusal before an invocation is read. Cerebellar CI uses only `entry.py inspect`; the separate full inert-graph tests and production `run` route are not invoked here. Both new checks use only the standard library, install no dependencies, and grant no execution authority. Their package documentation retains future dependency, input-rights, runtime and scientific requirements.

The OpenBMI source check authenticates its complete closure and builds trusted definitions using explicitly inert denying capabilities. Missing execution admissions remain; this package has no fixed BUILD_ONLY policy file. The check poisons numerical imports, subprocess creation and socket connections, and does not invoke execution, protected grading or the complete probability graph. Its package documentation retains native, scientific, rights and resource-history limitations. FIND-025 runs its documented standard-library discovery command against invented records; its empty authentic plan remains incomplete. Its two claim families and 16 output groups remain one assignment, with no numeric paper pass or scientific qualification. Neither command installs dependencies or runs a neuroscience study.

The [NEURAL-094 regional source](neural094/README.md) preserves one existing
assignment's whole-population primary and complete frozen-program/investigator-
policy/reference target-last comparison. Its full scope is 39 sessions, ten mice,
73 literal regional labels, 2,628 pairs and five seeds. This chronological
development-cohort and deployment-strategy comparison does not establish causal
anatomy, unseen-mouse generalization, equal realized compute or model-internal
neural understanding. No new assignment or scientific qualification is added.

The dedicated source job first authenticates the literal reviewed manifest, then
runs the direct eight-method standard-library portability suite:

```sh
python3 -I -B benchmarks/scientific_contracts/neural094/complete_regional/operator.py inspect --source-bytes 5851 --source-sha256 e3595f43bafff2400788ca62bddd30c7763ee7a9a7a83f35f4b92afdaa79d6be --read-bytes 378528 --write-bytes 4096 --seconds 30
python3 -I -B benchmarks/scientific_contracts/neural094/test_portable_source.py
```

The inspector reads the strict 35-file component without importing benchmark
modules. The tests copy its 29 source members into a temporary 33-file layout and
three capsules, check early refusals and run only tiny invented loader bodies.
They do not run numerical methods, a model, container, provider or neuroscience
study. Keep `-B` and keep generated files outside the closed component. Historical
installed-source output names do not certify registry installation or runtime
admission. Project-source MIT, separate upstream GPL software and external data
terms remain distinct; inputs, protected authority and native/resource/provider
qualification remain unavailable in this public source distribution.

The [NEURAL-035 closed-pair source](neural035/README.md) retains one existing
assignment's complete fixed-window endpoint and both original grade objects.
Its public dependency tree contains the ordinary code while two delivery records
and the protected input binding remain absent, without placeholders. Distinct
public documentation/source pins do not silently qualify old private receipts.
The package adds no investigator condition, significance test, scientific result,
installed-runtime claim or benchmark count.

Its dedicated standard-library job authenticates the actual strict ten-member
source inventory and exercises bounded portability and refusal checks:

```sh
python3 -I -S -B benchmarks/scientific_contracts/neural035/closed_paired_grading/operator.py inspect --source-bytes 1644 --source-sha256 01b9b3571f31971defadb1af2fb6b0e798ae36fc108fd93e13af899871daea37 --read-bytes 68537 --write-bytes 101295 --seconds 30
python3 -I -S -B benchmarks/scientific_contracts/neural035/test_portable_source.py
```

No numerical/native producer, protected scoring, model, container or authentic
input is executed by these checks. Original target-last custody, separate trusted
authority, post-cleanup deadline, rights and scientific gates remain unchanged.
