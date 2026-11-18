# NEURAL-099: paired current-trial observation and collection

This portable source implements two zero-label access conditions for `processed-regional-early-response-assumed-support-v1`. It defines observation release and prediction collection. Actual candidate execution, containment and scientific evaluation require a separately approved operator configuration; the package supplies neither private inputs nor execution authority.

| Condition | Current input | Labels and state |
| --- | --- | --- |
| `direct-structured-zero-label-current-trial-v1` | Exact structured timing and 100 preceding-history rates for every available region of the current trial | Zero demonstration, training or response labels; fresh native context per trial; no tools |
| `frozen-programme-zero-label-current-trial-v1` | Identical canonical observation bytes | Zero benchmark labels; frozen programme and initial parameters; fresh process per trial |

The exact nine fields of each profile are preserved in `CONDITIONS.json` and `CONTRACT.json`. The existing trained programme and competent regional-mean reference remain separate comparisons: they may select using three training folds and the next validation fold, then refit on four non-query folds. Their larger information budget and permitted within-animal sequential state remain unchanged. The zero-label pair performs no selection, training or refit. It does not implement a live agent investigating through tools. Matched inputs and comparisons with a trained reference do not identify a causal tool-use effect or general neural understanding.

## Complete condition and metrics

Production admission requires the exact selected case digest and all 26 source-declared animal groups, 26 sources, 5,238 trials, 49 available region cells, 1,387 retained good/MUA source clusters and 9,867 regional cases per arm. Each case has 100 response bins over [0,100) ms and history over [-100,0) ms. Every bin is half-open and nominally one millisecond. All supported cases remain required; absent regions are unsupported rather than zero targets. Five frozen hash-based folds organize grouping and completion; the zero-label pair does not fit cross-validation models.

The primary metric remains MSE averaged equally over animals, then available regions, then trials, then bins. Secondary metrics remain MAE with the same hierarchy and MSE after averaging each five adjacent 1-ms rates into 20 five-ms rates. Nominal rates use the exact `count * 1000 / source_cluster_count` convention and the pinned packet/scorer serialization. Represented absolute edge gaps do not redefine exposure. The collector reuses frozen prediction admission, preserving negative finite predictions and large finite integers without clipping, rounding or coercion. Collection itself computes no scores.

`observations.py` validates private metadata and projects only current history. `transports.py` builds the canonical payload. `access.py` preserves source-ID hash grouping and rejects partial production cohorts. `session.py` releases every available region of the current trial together, then requires both arms' complete predictions to lock before later history is read. Requests are copied, and prior requests or predictions are never supplied to later candidate contexts.

`collect.py` creates an exclusive private journal, persists its parent entry and fsyncs each write before advancement. Records bind the frozen procedure, exact observation hash, predictions and a fresh attempt nonce. Malformed, stale, incomplete or over-budget submissions end the whole attempt: no dropped cases, retry, resume, clipping or imputation. A `COMPLETE.json` pathname is provisional. Acceptance requires a successful trusted operator finish receipt, clean supervised closure and separate verification of the complete chain and artifacts. A late filesystem failure can leave a marker without a successful finish receipt.

## Package dependencies and operator manifest

`DEPENDENCIES.json` records package-relative origins under `deps/` and exact dependency sizes and SHA-256 values. `dependencies.py` authenticates those bytes before loading them. The frozen scoring, condition and packet algorithms are unchanged. Inventory paths describe package contents; they are distinct from the explicit absolute paths that a trusted operator supplies at runtime.

From the package root, the description interface is:

```sh
python3 -I -S -B paired/cli.py describe
```

`EXECUTION_MANIFEST.example.json` is a **GENERATED template**, not an authentic manifest or execution approval. Its paths are `/ABSOLUTE/OPERATOR/...` placeholders. Both procedure hashes and the canonical case-binding digest are clearly marked non-hex placeholders. The CLI rejects the procedure placeholders before opening private inputs. Replace them only with independently verified, frozen values for a separately approved study. Example message and journal limits illustrate finite fields; they allocate no storage and do not establish adequate capacity for a real run.

The packet profile and opaque packet digest in the example are the exact selected commitments. `CONTRACT.json` also records the exact case-file byte digest. The packet binding's `cases_sha256` instead hashes canonical ordered case metadata without a trailing newline; it is a different digest and must come from the verified private preparation receipt. No populated case paths, packet paths, private case records or signal arrays are distributed in this package.

A real manifest must bind the exact source snapshot, a study ID, both frozen procedures, complete private input bindings, fresh output storage, finite limits, and a runtime-supervisor/isolation admission reference. The native procedure includes frozen instructions/configuration; the programme procedure includes source and permitted initial parameters. A hash alone does not establish zero-label provenance, content, tool restrictions or fresh state.

After those requirements are independently satisfied, the trusted operator interface is:

```sh
python3 -I -S -B paired/cli.py serve --execution-manifest /ABSOLUTE/OPERATOR/EXECUTION_MANIFEST.json
```

`serve` handles begin, current, submit and finish operations in one JSONL session. It launches no model or programme and has no production subset flag. Study and procedure bindings are checked before inputs open. The evaluator authenticates the full private packet once, including response bytes, then projects only released histories. That internal authentication is not participant disclosure. Participants must never receive the controller, packet, journal, file descriptors or complete operator stream. The runtime caller's absolute-path, permission, single-link, regular-file, extent, cohort and checksum guards remain required. The operator must qualify filesystem/provider isolation, fresh candidate contexts or processes, resource supervision and saved completion evidence separately.

## Interpretation and validation limits

Only fixed instructions, frozen source and permitted initial parameters may persist between trials. Observation-dependent caches, files, provider memory, previous-query results and benchmark labels embedded in programme source are prohibited. Zero evaluator-supplied labels does not establish absence of public-data contamination or relevant pretraining. Timing-only access, rendered viewers, live tool agents and budgeted demonstrations require separate versioned conditions; missing history never silently changes the selected pair.

This endpoint forecasts processed early click responses under an explicit observation-support assumption. It does not establish recording continuity, physical stimulus-onset parity or unknown biological aliases. Source clusters are processed good/MUA recording objects rather than individual neurons; whole-session sorting may use retrospective information. Zero counts do not independently prove neuronal silence. The endpoint differs from the paper's normalized PSTH analysis.

The included tests use generated fixtures. Release validation must identify the exact packaged source and checks exercised; this document imports no private development review or historical run record. Generated checks do not qualify authentic observation exports, collection, isolation, model performance or scientific readiness. No authentic paired collection, baseline fit, model call or score is asserted by this source contract.
