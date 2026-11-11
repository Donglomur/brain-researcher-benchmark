# NEURAL-002: early marker-window stimulus information

This is an **inactive, unqualified source package** for one replacement assignment. The scientific question is: **Does the first 500 ms of software-marker-locked EEG contain reproducible stimulus-ID information in an unseen participant beyond prespecified context and temporal controls?** It uses32 participants and six nested task/speed cells, not six benchmarks. The endpoint is retrospective stimulus decoding. It does not measure speech comprehension, recognition correctness, physical auditory-onset calibration or pre-response neural understanding.

The prior MEG speech-intelligibility definition is retained byte-for-byte in the authoring history and inverse mapping. Root explicitly selected this different endpoint after source review showed the prior intelligibility labels were psychometric SNR-derived. PhyAAt measured-word alternatives remain documented but their listening-window/score clock join is unresolved.

## Fixed scientific contract

OpenNeuro ds007655 commit `d2e09f610d267b8b3679997f8bc4e52fe6ca402a`, descriptor DOI `10.18112/openneuro.ds007655.v1.0.2`. All32 people, tasks `dotcount`/`firstlast`, speeds15/30/40CPM. Every cell contains26 raw trigger IDs, each repeated twice. Nominal total9,984 trials. No authentic payload has been inspected by this construction phase, so usable counts remain unverified. A failed count/class/identity check blocks construction; exclusions require a separately reviewed contract revision, not silent reduction.

Step0 writes `sample=trigger+1` and `onset=trigger/600` with six decimals. The importer joins the event to the BrainVision stimulus marker by exact1-based sample and raw value, validates onset within0.501microseconds, and retains the exact source identity privately. Array windows start at `sample-1`:62×301 points, marker0–500ms inclusive at600Hz. No positional/minimum-length behavior joins. Do not use released cleaned derivatives, whose trial removals lose original identity.

Raw trigger ranges are1–26,27–52,53–78. A cell's output is the ordered26-class index into its raw range. No modulo conversion to shared characters or unverified cross-speed mapping. Task/speed are supplied context. Classifying task/speed is not this endpoint because their sequence is fixed in the experiment.

The500ms window has an ERP-analysis precedent, but whole-character acoustic coverage and perfect26-way identifiability are not established. Shared acoustic prefixes may limit achievable accuracy. Prefix-identifiability and order controls are an explicit qualification gate; low performance must not be equated with failure to understand complete auditory sequences.

**New preprocessing amendment:** remove PO4 and TP8 for every person by setting their slots to zero; average-reference the remaining60 channels independently at each sample. Retain the common62-slot array. This handles documented bad channels in sub-13/14/15 without person-dependent masks or unspecified neighbor interpolation. It intentionally departs from author interpolation. No additional filtering, ICA, normalization across query people or behavior-dependent cropping. Original acquisition filters remain part of the dataset. Window/code/header scaling and channel order must be authenticated before native use. A matched premarker control uses the301 immediately preceding samples.

## Split, score and controls

All32 leave-one-person-out folds are mandatory. The held person's two tasks, all speeds and repetitions stay together. Query labels are private. Fixed baseline hyperparameters do not tune; any added tuning uses only the31 training people with grouped validation. Candidate modes are frozen program and case-adaptive under equal frozen input/tools/compute budgets, receiving the same unlabeled312-trial held-person batch. Reset workers per person and expose no grading feedback.

Primary score is balanced accuracy per person/cell, equal-six-cell mean per person, then equal32-person mean. Report192 cell scores/confusion matrices, person scores, complete coverage and secondary log loss. Ties choose the lowest class index. The scorer rejects malformed probabilities, duplicate/missing/unknown IDs, nonfinite values and incomplete cohorts/classes. A paired participant bootstrap describes candidate/reference differences; it is not by itself a scientific significance or frontier claim.

`morse_baselines.py` implements equal-person fixed shrinkage ERP centroids, class priors and nuisance centroids using training data only. `reference_pipeline.py` composes all192 fits and full scoring. `controls.py` shuffles training labels only within person/cell. Premarker signal uses the same complete fold route. Order-only is a trusted diagnostic from source chronology. Duration-only and response-only are explicit unavailable routes until an independent behavioral join/timing/code certificate exists; raw response codes must use a frozen one-hot vocabulary. None of these nuisance fields enter candidate inputs.

Before interpreting a positive result, compare prior/order/premarker/permutation controls, the EEG reference and authenticated response/duration controls. A retrospective result can contain acoustic, motor, condition-order and residual artifact information. It does not establish semantic understanding or a benefit over original paper performance.

## Source APIs and remaining gates

- `provider.Recording`: future authenticated four-file BrainVision intake. Verifies exact pins, bounded ordinary files, raw format/scaling, event/marker identity and recording extent. It reads no file at import. Supports explicit little-endian IEEE_FLOAT_32/INT_16 multiplexed native data; unknown encodings fail closed. Exact pinned Git-annex content bindings and actual parser compatibility remain intake gates.
- `importer`: text-only parsers plus full cohort/target schema. No behavioral primary target.
- `windows.extract`: fixed extraction and common preprocessing through a certified native reader.
- `packets.prepare` / `packets.fold`: full-cohort preparation and strict held-person projection. Opaque IDs use a private random nonce and are shuffled by keyed identifier. Withhold source filenames, sample/onset, chronology, trigger, behavior, duration and variable length.
- `scorer.score`: trusted aggregation after all32 folds; `paired_interval` uses person units.
- `reference_pipeline.run_reference`: full baseline composition, source only; no candidate or API model launch.
- `task_operator.py inspect`: reads source metadata only. It is the only CLI operation.

The Python functions are trusted operator code, not a hostile-process sandbox. A separate qualified worker runner, authentic intake, packet hashes, contamination/exposure audit, resource limits, native reference/control execution and independent scoring replication remain required. Generic execution and admission flags are false. No GPU/model/API study has run.

Inspection after root installation:

```sh
python3 -B benchmarks/neuroscience/neural-002/task_operator.py inspect
```

Source engineering controls use explicitly invented data and cannot qualify the benchmark. The original MATLAB code remains an external provenance reference: dataset CC0 is documented, but a separate software grant was not located, so this package does not bundle those bodies. `SOURCES.json` records exact external source bodies and metadata pins.

Nominal float32 window storage is745,285,632bytes (about0.694GiB), excluding raw recordings, train/query copies, premarker controls, metadata and overhead. Full in-memory preparation and numerical fitting require an independently reviewed runtime allocation. These are planning arithmetic, not measured acquisition costs.

## Selected early-information interpretation

Root explicitly selected this narrower information assay after the independent timing audit. All 32 folds, six nested cells, 26 raw ID labels, 301 samples and the balanced-accuracy metric remain unchanged. All ten Python modules are byte-identical to the engineering-reviewed predecessor. No scientific or numerical result is added.

Report raw scores **together with paired participant gains against prior-only, order-only, premarker EEG, training-label permutation and a validated competent EEG reference**. The supplied shrinkage/nuisance centroids are reference candidates; their adequacy is unqualified. Freeze and validate control capacity/reliability using training-only development, retain matching inputs/budgets, and establish authenticated response/duration nuisance controls before interpretation. The unchanged source provides per-arm composition and paired-interval helpers, not an executed all-control report. A null or inconclusive outcome is valid.

The information-opportunity/reliability gate remains open. If source timing establishes that all relevant delivered prefixes are identical, reconsider primary use or keep this window only as a negative control. Do not guess a decoding ceiling from nominal CPM, assume standard Morse timing, or choose an arbitrary longer window. Distinct symbolic or physical prefixes also do not guarantee reliable EEG discriminability.

This endpoint makes no complete-character, comprehension, physical acoustic-onset or pre-response claim. The independently reviewed 3,912-byte public stimulus dictionary is source metadata, not a participant target table. Its addendum and the timing audit are pinned in SOURCES.json; no audio, EEG, authentic event/header or behavioral target payload is included. Final scientific qualification requires the declared evidence even though the source definition has now been selected.
