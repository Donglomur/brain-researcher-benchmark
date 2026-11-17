# Original behavioral source statistic

This standalone, standard-library component makes the original three-model cohort reduction executable from the public checkout. The retained registered runtime depends on unavailable historical modules. This component ports only the source reduction; it does not replace that runtime, recompute likelihoods, authenticate fitted parameters, or register an improvement evaluator.

The original behavioral task covers **25 participants, 120 trials each, and three separately fitted models**. It has no held-out behavioral split. All 75 participant/model log likelihoods are required. EEG participants, source regressors, and a new prediction split are outside this calculation.

Reproducing the original findings and exceeding them on the same task are separate, first-class outcomes. This component supplies arithmetic needed for the reproduction route. Eventual paper-plus-data and paper-plus-data-plus-author-code conditions must use the same complete cohort and scoring, with code–paper discrepancies explicitly resolved. It does not itself deliver or qualify those paired conditions.

## Recovered source convention

The paper-linked author commit is `4e0953016e65961327ba5be1075f5aad52f3ba40`. The task-pinned commit `80418e5d1949631b0e2b54432e6b6956773c43da` adds only `LICENSE`: all 683 preexisting blobs have identical Git identities. Both complete source trees and the output-free notebook view were checked against existing source receipts without fetching new data.

The consequential source is **`model_validation.ipynb`**, rather than the exploratory `data_fitting.ipynb` cited by the current improvement contract. Cells 8–10 each append 25 saved optimizer maxima to `LL`, `LL_rl`, and `LL_m_rl`. Cell 26 calculates:

```python
BIC_ai = -np.sum(LL)*2+5*np.log(6000)
BIC_rl = -np.sum(LL_rl)*2+2*np.log(6000)
BIC_m_rl = -np.sum(LL_m_rl)*2+3*np.log(6000)
```

Cell 28 plots those three quantities in the order active inference, model-free RL, model-based RL. [The immutable author notebook](https://github.com/andlab-um/FreeEnergyEEG/blob/80418e5d1949631b0e2b54432e6b6956773c43da/code%20for%20data%20analysis/model_validation.ipynb) and [SOURCE_PINS.json](SOURCE_PINS.json) identify this route precisely.

The source therefore applies **one** penalty with `k = 5, 2, 3` after summing independently fitted participant likelihoods. It fixes `N = 6000 = 25 × 120 × 2`, including forced first-choice opportunities. This is not established standard BIC for 25 independently parameterized models. Multiplying `k` by 25, using observed informative-choice counts, summing participant BICs, or averaging the likelihoods would change the source statistic. This component makes none of those substitutions.

The use of `math.fsum` and `math.log` preserves the mathematical expression with stable standard-library arithmetic; bitwise identity to a historical NumPy environment is not asserted. Natural logarithms produce a dimensionless criterion; input log likelihoods are in nats. A negative active-inference-minus-comparator result means the active-inference source statistic is lower for the supplied panel. It does not establish superiority, fit validity, or biological mechanism.

## Operator interface

Supply a UTF-8 CSV with this exact header and all 75 unique pairs. Participant IDs are integers 1–25 and models are `active_inference`, `model_free_rl`, or `model_based_rl`.

```text
participant_id,model,log_likelihood
```

Each likelihood must be the finite, nonpositive natural-log choice-probability sum for the participant's original full block, computed under the separately authenticated source model and likelihood mask. The reducer cannot establish that provenance from a scalar. Missing fits, duplicate pairs, unknown models, invalid numbers, or a 23-person cohort cause rejection rather than incomplete-cohort aggregation.

```sh
python3 -B source_statistic.py --input /operator/panel.csv --output /operator/source-statistic.json
```

The result includes the source penalties, likelihood sums, all three source statistics, signed cohort contrasts, and the SHA-256 of the actual CSV. Results must remain in operator evidence outside Git. The command creates a new output file and refuses to overwrite one. It never launches submitted code or reads source optimizer histories.

## Qualification and unresolved work

Qualification is **a source-grounded arithmetic component with generated software controls**, not a qualified benchmark or a reproduced publication result. Seven generated tests passed through the shared test pool: exact source penalty, complete-cohort rejection, ordering, CSV transport, invalid values, arithmetic overflow, and CLI output preservation. The test receipt and exact file freeze are supplied separately to the coordinator. No authentic likelihoods entered these checks.

This recovery resolves the literal notebook aggregation and the paper/catalog code lineage. It does not establish the numerical Figure 4c baseline, publication-to-saved-fit identity, historical dependency/optimizer equivalence, or which interpretation of the code–paper discrepancies should govern a scientific improvement claim. The literal model-free integer learning state also differs from the paper's real-valued update description. The author source and paper must be reconciled before admitting candidates, rather than silently repairing the model or penalty.

No authentic participant array or optimizer history was decoded, no fitting or model trial was run, no new source payload was downloaded, and no empirical result is emitted by this change. Existing exposed data remain exposed. EEG exclusions and trial mapping, the full supporting calibration scope, meaningful effects, participant-level uncertainty, and protected method-selection/admission remain unresolved. The authoritative task and improvement contract are unchanged; their source-convention descriptions should be updated only through integration review.

Prior source reduction existed in private historical calibration tooling. This is a portable recovery of that narrowly scoped arithmetic and its author-source evidence, not a new algorithm or a claim that earlier calibration established paper improvement.
