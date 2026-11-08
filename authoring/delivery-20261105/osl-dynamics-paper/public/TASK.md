# Reproduce the osl-dynamics toolbox paper and test held-person improvements

Task `PAPER-paper-signal-add-004` covers the complete empirical scope of **osl-dynamics, a toolbox for modeling fast dynamic brain activity**, https://elifesciences.org/articles/91949 (version-of-record DOI10.7554/eLife.91949.3). The native implementation is the paper-cited Software Heritage revision `cded3b2ea95efef7b6c089c5e111fd565b716922`, declared version1.2.dev12. This differs from the later canonical repository pin and from PyPI1.2.11; they are not interchangeable.

This is a **partial construction package**. It contains original source, deterministic preparation code, an exact Gaussian-HMM artifact scorer, six-branch native capture instrumentation, a fixed-fit numeric audit, and invented checks. It contains no authentic neural recordings, newly fitted models, private scientific reference or validated execution environment. A fixed-fit audit is not independent-fit reproduction, and held-person likelihood is not the paper's whole scientific claim.

## Required scientific scope

| Branch | Figure | Complete observations | Original method |
|---|---|---|---|
| ctf_bursts |1|65people, left motor region,100Hz|3-state TDE21 HMM; burst durations/intervals/counts/amplitudes, spectra, envelope relations|
| elekta_ae |2|19people ×6runs,38Giles parcels,250Hz|8-state envelope HMM; spatial states and task-evoked state probability|
| elekta_tde |3|same114 complete runs|8-state TDE15/PCA80 HMM; spectra/networks and event responses|
| ctf_tde |4|all65people,38parcels,250Hz|8-state TDE15/PCA80 HMM; temporal/network structure and age relations|
| ctf_dynemo |5|same65people|7 simultaneous continuous modes; regression spectra, coactivation and age relations|
| ctf_static |6|same65people|Welch power/coherence plus amplitude-envelope correlation across four bands|

`NATIVE_RECIPE.json` binds exact scripts, default hyperparameters, endpoints and event codes. Figs7–12 are methodological/simulation illustrations, not additional empirical cohorts. A complete reproduction should also recover those demonstrations from the cited source, without treating synthetic illustrations as new biological evidence. Do not replace any of the six branches with a toy, a reduced cohort, a different atlas or published fitted-result matrices.

## Two access conditions

A receives the paper, the same authenticated complete task inputs, and this benchmark's contract/reference mathematics. B additionally receives the unchanged official source in `author_paper_archive`. The operator stages each condition using `private/stage_access.py` and `ACCESS.json`; the union package is not an A mount. `VIEW.json` records exact selected source bytes. The original paper body is provisioned identically in both. Data and scientific targets are not supplied by this source stager.

No official pretrained checkpoints, `inf_params` or deposited spectra are candidate inputs. Native replay may use the complete reproduction cohort. Held-person prediction uses separate fresh execution contexts: all runs from a query person remain private; no other fold's inputs/targets are mounted. Access to pooled cross-validation directories is prohibited. Isolation has not been implemented or verified here.

## Native replay, corrected sensitivity and improvement are distinct

Run the five stochastic branches in three independent sets of ten complete attempts; choose the smallest **training** free energy within each set and retain every failed attempt. Original seeds are not recovered, so exact stochastic equality is not promised. Static analysis is a deterministic branch, not30 extra fits. The original scripts remain unchanged. `native_capture.py` creates source derivatives by adding observation-only array captures at specified native endpoints. A generated AST check proves all other statements remain identical. No such derivative has been scientifically executed.

Three source issues require explicit reporting. Dynamic HMM/DyNeMo numeric age assignments are ≤34 versus >34, but plotting strings reverse Young/Old; static code instead divides <34 versus ≥34. Preserve the literal outputs, and report a separately named ≤34-young harmonized sensitivity. Elekta's original event function returns114 run means; its permutation helper treats that axis independently. Preserve literal replay, then report a separate corrected analysis averaging six runs per person, with19 participant sign flips. `biological_controls.py` defines a prospective two-sided max-absolute-mean control with1000 PCG64 signs and conservative +1 pvalues; it is not claimed identical to native glmtools inference.

The native HMM `evidence()` helper places stationary probabilities directly in a log-prediction array. The prospective scorer uses **log(initial probability)**, including structural zeros. Native free-energy selection is a different function and is not silently changed. Do not describe evidence from either implementation as empirical validation of the other.

The numeric mode `native_artifact_audit` checks a fixed set of central native arrays against a trusted fixed-fit reference, including exact undefined support. Panel/person/length identities are generated by `output_contract.py`; operators cannot select a favorable subset. The error is `abs(candidate-reference)/(scale+abs(reference))`, averaged over entries, then items within panel/person, people, and panels. Scales must be declared in the case contract before candidate work; no calibrated scales/references exist yet. Positive errors too small for binary64 remain tagged positive_underflow after exact-ratio aggregation, never zero. Undefined disagreement makes primary null; wholly undefined items supply no zero-error credit. This audit preserves three burst states, eight HMM states and seven continuous DyNeMo modes. It does not match independently fitted permutations. Full spectrum/axis capture, training-only correspondence, stochastic-fit variation and acceptance calibration are still required for whole-paper reproduction.

## Prospective held-person HMM condition

The four HMM branches additionally admit a concrete improvement endpoint. Fixed five-fold person assignments are SHA256-ranked and round-robin, using `osl-full-paper-fold-v1:<cohort>:<original person id>`. All65CTF or19Elekta people participate; all six Elekta runs stay together. No age, response, fit quality or result selects folds. Report each branch separately, both A/B conditions, all folds and all three training-selected fit sets; a single fold is not completion.

The operator fits standardization/PCA on training people only, freezes its byte identity, and applies it to query runs. Embedding never crosses a real run boundary. `preprocessing.py` specifies a prospective channel-major, oldest-to-newest embedding; it does not assert native stacking/normalization equivalence. Its fixed rank requirement is s[d−1]/s[0]>1e−10; insufficient training rank invalidates the whole case instead of dropping dimensions. AE representation requires a still-unvalidated training-only envelope-preparation integration. Query-specific scaling, dual estimation, state matching, fitting, hyperparameter/seed selection or stopping are forbidden in this condition. Offline centered embedding/envelopes do not imply causal online availability.

Submit one Gaussian HMM with the fixed branch's dimensions/states: bursts21/3, AE38/8, networkTDE80/8. Output ordinary JSON parameters `means`, `covariances`, `transition`, `initial` in `submission.json`. Covariances must be symmetric positive definite; simplex rows must sum to1 within1e−10, with structural zeros allowed. No scoring-time regularization or clipping. Parameter adaptation is permitted during training within the fixed family/budget; assessment observations are never candidate inputs.

The private scorer recomputes the exact finite-state Gaussian marginal likelihood, including Gaussian constants and a fresh initial distribution at every run. Within person, sum run log likelihoods and divide by all retained represented samples; then average people equally. It reports candidate and fixed training-only static-Gaussian nats per observation and their difference. `reference_hmm.py` specifies a native-family training comparator on full training-person/run represented arrays; it is unexecuted and never receives query arrays. The common static comparator uses a prospective fixed ridge1e−6×mean training variance. The representation and comparator must be identical for every candidate/control in that case. Overlapping delay vectors define an embedded-space objective, not the raw continuous signal's joint density. Higher gain is better; zero/negative gain remains valid, and no binary success threshold is invented.

Train-on-surrogate controls must use frozen seeds and the same fit budget: common-phase randomization preserves cross-spectra, independent-phase disrupts them while preserving marginal periodograms. Both are assessed on the identical **real** held-person signals. `phase_randomize` is source only; no authentic surrogates have been generated. State occupancy, spectra and task/age effects remain separate scientific diagnostics. DyNeMo ELBO, posterior reconstruction, AE density and TDE density are not pooled with HMM marginal likelihood. A valid comparable DyNeMo held-person extension remains an explicit gate; it is not silently replaced with an HMM.

## Submission and grading interface

`submission.schema.json` gives syntax; the complete fixed case contract and `score.admit` enforce exact identities, full rosters and mathematical constraints. JSON is strict UTF-8, with no duplicate keys, NaN/Infinity, object arrays or candidate code. All candidate fields are admitted before the private loader. Input JSON is at most16MB; each pinned private float NPY is at most128MB, with header shape/byte extent checked before allocation. A new output path is required. Failure classes distinguish invalid candidate, operator error and valid scored output; no failed/partial run receives a scientific score.

Future trusted invocation:

```
python private/score.py --submission submission.json --contract case.json --contract-pin SHA256 --reference private_reference.json --reference-pin SHA256 --out new_report.json
```

Those case/reference files do not currently exist. The CLI does not establish training provenance, isolation or runtime qualification. All benchmark scientific claims remain unqualified until the full inputs, prospective bindings, native captures, comparators and executor are completed and independently tested.
