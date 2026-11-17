# Plexus prospective held-plate evaluator

This package implements the statistical evaluation component of `PAPER-CANDIDATE-20261114-PLEXUS`: a frozen complete-screen well census, exact held-well prediction coverage, plate discrimination and calibration, gene/line score-separation tests, and paired network-versus-comparator uncertainty. It runs with Python 3.10+ standard library only. It does not train Plexus, consume released embeddings as benchmark inputs, execute an authentic screen, or establish historical reproduction. Scientific qualification and submission readiness remain unknown.

## Historical source versus this prospective policy

The [final Figure 4 caption](https://www.nature.com/articles/s42256-025-01156-x/figures/4) describes elastic-net discrimination of each dual-guide vector against non-targeting controls, with two four-well splits reported separately for WTC11 and Patient lines. Its AUROC 0.8 cutoff is not a calibrated false-discovery procedure. The [pinned Figure 4 source](https://github.com/pgrosjean/plexus/blob/69ccecbcc00f8462c8ce2a9d699be09f4c53ed66/figure_scripts/Figure4/figure_4.py) splits unique well locations in half and reverses the train/test roles. It fits a scaler before that split and evaluates cells. Historical pre-split fitting must be preserved and disclosed in a future historical reproduction.

This package deliberately implements the separately registered **prospective whole-plate/batch endpoint**. The manifest fixes the 52 genes, all released lines and well census; models and statistics must fit training wells only. Wells, rather than cells, receive weight. Batch and plate identities cannot cross split roles. No historical metric is overwritten. The source discrepancy between v1 data availability and v2 bibliography remains unresolved: this evaluator binds v2 DOI `10.5281/zenodo.15809433`; the authentic release census still requires independent reconciliation.

The [final Figure 6 caption](https://www.nature.com/articles/s42256-025-01156-x/figures/6) establishes WT and V337M mutant strata in both WTC11 and Patient backgrounds. Its Mann–Whitney U description differs from the pinned Figure 6 `ranksums` call, another unresolved historical significance gate.

The official source revision is `69ccecbcc00f8462c8ce2a9d699be09f4c53ed66`; software is MIT, dataset declaration is CC-BY-4.0. No third-party source body or data is redistributed. `sources.json` records exact reviewed source representations and limits.

## Inputs and frozen admission

The CLI requires a manifest JSON, its **independently frozen canonical JSON SHA-256**, and submission JSON. `canonical_hash` uses UTF-8 JSON, sorted object keys, compact separators, ASCII escaping and no nonfinite numbers. The pin must come from the curator before evaluation; calculating it from an untrusted submission defeats this boundary. Duplicate JSON fields are rejected. An unchanged hash establishes identity only, not authenticity.

The manifest has these fields:

| Field | Meaning |
| --- | --- |
| `task_id` | `PAPER-CANDIDATE-20261114-PLEXUS` |
| `contract_sha256` | `125009ce994e355a227ce6cf87ab2923a43336ea7dbfe216afdadbcc46b25ef7` |
| `dataset_record` | `10.5281/zenodo.15809433`; v1 is rejected |
| `genes` | Exactly 52 distinct approved gene identifiers, all represented in the census |
| `cell_lines` | Exactly `WT-WTC11`, `Mutant-WTC11`, `WT-Patient Line`, `Mutant-Patient Line`; these canonical stratum names require a source-audited mapping |
| `population_scope` | Human-readable complete-release/census identity |
| `population_source_sha256`, `cell_line_mapping_sha256`, `split_plan_sha256` | Pins of independently audited census source, four-stratum metadata mapping, and frozen grouped split plan |
| `exchangeability_design_sha256`, `exchangeability_approved` | Pin of the curator's experimental randomization justification and explicit Boolean approval |
| `wells` | Every released well, including train/dev/test, controls, and excluded wells in all four cell-line strata |

Each well records `cell_line`, `batch`, `plate`, `well`, `guide`, `gene` (null for controls), Boolean `is_control`, `role` (`train`, `dev`, `test`), Boolean `eligible`, `n_cells`, `exclusion_reason`, and `exchangeability_block`. Its unique identity is `(cell_line,batch,plate,well)`. Eligible wells need positive cell counts and null exclusion reason; exclusions need explicit reasons and remain in the output. Cells are descriptive counts, never independent replicates. Batch and plate IDs must identify physical units globally, not reusable local names: a batch or plate cannot cross roles even across lines, a plate cannot alias multiple batches, and a physical `(plate,well)` cannot appear under multiple line labels. Batch independence is assumed within each line analysis; its scientific basis belongs in the frozen split/design evidence. Exchangeability blocks are automatically scoped inside `(line,batch,plate)` and never cross these boundaries. Merely sharing a plate does **not** establish exchangeability.

The submission binds `manifest_sha256`, `policy: "prospective-held-plate-v1"`, `fdr_alpha: 0.05`, `models`, and `scores`. Required model keys are `network`, `single_cell`, `manual_features`, `nuisance_only`, and `label_shuffle_refit`. This enforces the three scientific comparators plus nuisance and shuffled-training-label controls on identical held wells. The network-context ablation must use the same inputs and a matched parameter/tuning budget; those properties remain artifact-audit responsibilities.

Each model records SHA-256 fields `source_sha256`, `configuration_sha256`, `fitted_artifact_sha256`, `tuning_plan_sha256`; `fit_wells` and `statistics_wells` are lists of four-element well identities drawn only from eligible training wells. Set `checkpoint_exposure: "train_only"` and `frozen_before_held_labels: true`. `input_basis` must be `processed_neuronal_inputs` except `metadata_only` for the nuisance comparator. The shuffled-refit comparator also records `training_label_shuffle_plan_sha256`. These checked declarations cannot prove that a submitted checkpoint actually followed them; protected artifact review is still required. Inner grouped tuning, equal budgets, complete neuronal inputs and hidden-label custody are necessary additional audit gates.

Each score row has `method`, `target_gene`, `cell_line`, `batch`, `plate`, `well`, `probability`. Probability means the frozen gene-versus-negative-control model's probability of the target perturbation, in [0,1]. For **each method and each of 52 genes**, scores are required for every eligible held well with that gene and every eligible held control well. Controls therefore have a different score entry per target model. No training, excluded, other-gene, duplicated, or missing prediction is admitted. Predictions are already well-level; this package intentionally does not invent an unverified cell-to-well reduction of released model embeddings.

## Estimands and numerical policy

For each gene, line, and plate, AUROC is the probability that a random target well's score exceeds a control well's score, with ties receiving one half. Single-class plates have unavailable AUROC and are counted, never pooled with another plate to manufacture a two-class endpoint. Reported Brier score is the mean squared probability error at the **observed plate prevalence**, which is included alongside it. Calibration also includes ten fixed-width probability-bin ECE, negative-control mean score, Brier score, and fraction at or above 0.5. Calibration values are descriptive under the sampled well prevalence, not population-adjusted clinical risk estimates.

The gene/line AUROC is the equal-weight mean over estimable plates. Gene/line Brier averages all available plates, including explicitly marked single-class plates. The score-separation estimate is mean target probability minus mean control probability within each two-class plate, averaged equally over plates. It is a **predictive score separation**, not a biological effect size, cross-line effect, or the paper's phenotype estimator. All guides contribute to their gene's well-level population; guide/plate metrics are also returned using the same gene classifier. These slices retain guide heterogeneity and are not historical separately fitted dual-guide models.

Conditional on independently established well-label exchangeability, the one-sided randomization null permutes target/control labels within the curator's frozen blocks, preserving each block's class counts. The statistic is equal-plate score separation. Scores remain fixed; this is distinct from the `label_shuffle_refit` training control. The Monte Carlo tail probability is `(1 + count(null >= observed))/(B + 1)`. With no approved exchangeability or no mixed-label blocks, the p value is unavailable. All 52 × all four line endpoints remain in each method's multiplicity family; unavailable endpoints receive a conservative multiplicity p value of 1. Benjamini–Yekutieli adjustment at fixed alpha 0.05 permits arbitrary dependence, including shared controls. This is a prospective choice, justified by those dependencies, not the paper's procedure. Families are separate per method; conclusions across all five families require further multiplicity planning.

`permutations` defaults to 49,999; the report exposes its minimum attainable p value. Lower engineering settings can make any rejection impossible in the complete family. A high number of discoveries alone does not establish improvement. The evaluator does not select methods, hyperparameters, genes, lines, FDR alpha, seeds or eligibility using held outcomes.

Uncertainty resamples complete batches within each line, keeping all plates in a sampled batch together. The estimate remains equal-plate weighted; duplicated sampled batches retain all original plate contributions. A percentile 95% interval requires at least two independent batches, otherwise it is unavailable. Two batches permit computation but are weak evidence, and no coverage guarantee is claimed. The report provides these intervals for score separation and paired per-plate network-minus-comparator AUROC, Brier and separation. Brier contrasts retain all eligible plates, including single-class controls-only plates; AUROC and separation contrasts use two-class plates only, with the population stated per metric. Positive AUROC differences and negative Brier differences favor the network method. These comparison intervals are descriptive, not a multiplicity-corrected superiority test. Cell-line transfer remains a separate unimplemented endpoint.

## Execution and outputs

From the package directory:

```sh
python3 plexus_evaluator.py --manifest /absolute/approved-manifest.json \
  --manifest-sha256 APPROVED_CANONICAL_SHA256 \
  --submission /absolute/predictions.json --output /absolute/report.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The report includes every method × gene × line endpoint, plate metrics, guide/plate slices, paired comparator intervals, complete exclusions, provenance hashes, inference resource settings, and explicit unavailable statuses. It always reports scientific qualification `unknown`, historical reproduction `not_established`, and native execution `not_performed`. The test helper `controls()` in `tests/test_evaluator.py` constructs a full 52-name generated example demonstrating the exact input shape; its names and values are engineering controls, not an authentic screen or source-derived gene list. Tests exercise arithmetic independently, leakage, coverage, unavailable cases and the actual CLI.

## Requirement mapping and retained gates

| Registered requirement | This deliverable |
| --- | --- |
| Complete 52-gene/all-line/plate/well screen | Enforces the pinned declared census, all52 table rows per line and all method prediction populations; authentic census and guide mapping still held |
| Whole plate/batch and well protection | Rejects cross-role batches/plates, duplicates and non-training fit/statistics lineage; actual artifact custody still held |
| Network, single-cell, manual and nuisance/shuffle controls | Exact matched score coverage and paired statistical comparison; native fitting and budget parity still held |
| Plate AUROC, calibration, frozen FDR | Implemented under the explicit prospective policy above |
| Grouped uncertainty and biological replication | Complete-batch intervals; no cell-level replication; independence needs source evidence |
| Full phenotype effect/significance and historical screen estimator | Predictive score separation only; historical per-guide classifier, normalization and biological phenotype reference not implemented |
| Held-plate reproducibility and cell-line transfer | Plate/batch heterogeneity visible; independent validation/retest and explicit cross-line transfer protocol still held |
| Data/code/reference rights and identities | v2/pinned-code/contract preserved; archive-to-code equivalence, release population and final-paper preprocessing comparison remain unresolved |

No authentic data, models, archive, checkpoints or protected reference outputs were acquired. The code neither downloads inputs nor calls external services. Generated controls establish implementation behavior only. A curator must resolve the remaining source gates, freeze a complete authorized census/splits/design, and independently audit native training/reference artifacts before any benchmark result can be scientifically qualified.
