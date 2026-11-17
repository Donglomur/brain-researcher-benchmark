# MARBLE paper-improvement admission and extension diagnostics

**Same-task paper improvement is source unresolved.** This additive component belongs to existing `PAPER-paper-method-034`; it creates no task ID and changes no original task, score, heldout or grader. Reproduction is calibration, not success. A different split or local baseline cannot count as surpassing the paper.

This release makes the available preparation work executable: it authenticates the selected public source dependencies, emits exact ordered output-support metadata, checks an operator-supplied official source checkout against existing pins, and compares complete paired reports from the existing grader. It cannot launch models, read labels, load checkpoints or award historical-paper/SOTA improvement.

Read [SOURCE_FINDINGS.md](SOURCE_FINDINGS.md) for the primary-source findings. [BASELINE_MANIFEST.json](BASELINE_MANIFEST.json) identifies official author code and checkpoint routes while retaining missing result/provenance fields. [CURRENT_COMPARATOR.json](CURRENT_COMPARATOR.json) keeps current-best status unknown and records a concrete later comparator that fails exact-task comparability. [EPISODE.json](EPISODE.json) freezes the old extension's support, permitted changes, access conditions and prospective resource ceilings. Its four-rat chronological clean/half-neuron comparison is explicitly separate from the published Figure5d comparison.

From the repository root, using an existing Python3.11 interpreter:

```sh
python3.11 -I -B benchmarks/paper/PAPER-paper-method-034/implementations/paper-improvement-episode-v1/episode.py inspect

python3.11 -I -B benchmarks/paper/PAPER-paper-method-034/implementations/paper-improvement-episode-v1/episode.py prepare-interface --destination /ABS/FRESH_METADATA_DIRECTORY

python3.11 -I -B benchmarks/paper/PAPER-paper-method-034/implementations/paper-improvement-episode-v1/episode.py audit-author-source --author-root /ABS/EXISTING_OFFICIAL_CHECKOUT

python3.11 -I -B benchmarks/paper/PAPER-paper-method-034/implementations/paper-improvement-episode-v1/episode.py require-ready
```

`require-ready` deliberately exits2 and reports open gates. There is no attestation switch that promotes this release to ready. Preparing metadata does not create a runnable input packet. The combined original pickle must never be mounted into candidate inputs because it contains query behavior labels. The source audit reads only the17 existing pinned official source/notice roles, including the16 external bodies; it executes none. Missing or changed source is reported as unadmitted. No downloads or installation occur.

`prepare-interface` writes two JSON files in a fresh directory. Their32 output descriptors preserve every original animal, population condition, embedding dimension and train/query slot. Compact original-row intervals and ordered-identity digests make row identity reviewable without opening neural observations or targets. The actual embeddings and candidate manifest must still satisfy the sibling component's existing interface.

The bounded post-grader interface is:

```sh
python3.11 -I -B benchmarks/paper/PAPER-paper-method-034/implementations/paper-improvement-episode-v1/episode.py compare-grades \
  --grade-a /ABS/OPERATOR_GRADE_A.json --grade-a-bytes REVIEWED_BYTES_A --grade-a-sha256 REVIEWED_SHA256_A \
  --grade-b /ABS/OPERATOR_GRADE_B.json --grade-b-bytes REVIEWED_BYTES_B --grade-b-sha256 REVIEWED_SHA256_B
```

Use independently reviewed report identities, not hashes substituted after changes. This checks complete fixed support, finite values, aggregate arithmetic, identical comparator banks/scores/artifacts across A/B, and all candidate/reference artifacts before comparing. It reuses the exact existing `score_core.improvement` function. It does **not** call `score_core.score`, fit its decoder, or read its protected label inputs. The signed mean-error differences are useful effect-size diagnostics. Median and descriptive consistency cannot replace the primary mean-error endpoint. Every scientific-win field remains null because a report's declared provenance cannot establish historical parity, native competence or current SOTA. The earlier grader's own Boolean remains a prospective-extension diagnostic.

The extension's future limits are eight development configurations and one final submission per access arm, seed0, one GPU,48GPU-hours,192CPU-core-hours,72wall-hours,24GiB GPU memory,64GiB host memory and50GiB scratch, with200,000 LLM output tokens. All failed/interrupted work counts. The48-fit reference bank has a separate matching48GPU-hour/192CPU-core-hour ceiling and no tuning. These are fixed prospective ceilings, not runtime measurements or spending/execution authority. Current authorized fits are zero. Same-task source resolution may require a separately reviewed task-specific resource contract; the extension caps do not authorize that work.

The A/B arms receive the same paper/data and budgets; only B receives official code. A single candidate configuration is selected from development feedback, then frozen before original query evaluation. Candidate representation fitting is unsupervised; the fixed decoder receives training labels. CEBRA-behavior's additional supervised training is explicitly separate. Candidate program custody, network isolation, metering, runtime and all reference provenance remain required.

Construction checks use invented metadata and scores only:

```sh
python3.11 -I -B benchmarks/paper/PAPER-paper-method-034/implementations/paper-improvement-episode-v1/test_episode.py
```

These checks establish input rejection and diagnostic behavior. They establish no empirical baseline, difficulty, accuracy gain or scientific readiness. The initial test invocation exposed macOS's temporary-directory symlink alias; the test fixture now resolves its own temporary root, while production link refusal remains intact.

Integration is additive. Keep this component classified as preparation plus extension diagnostics. The global improvement contract should mark the same-task MARBLE objective `source_unresolved` until authentic original comparison evidence closes; do not wire the extension Boolean as active paper success. No global catalog/source-ownership edit is included in this commit.
