# Reward-spacing behavioral reconstruction

Verified local file scoring and program execution for Figure 1 e/g/h/k, covering 38 mice and 309 sessions. The scorer checks trial values, source eligibility, mouse endpoints and uncertainty separately. Wrong finite answers receive measured errors; missing required numbers produce incomplete coverage.

The 18 numerical controls and eight program controls passed. The ordinary program interface then matched the complete positive score, and the common CLI matched the complete valid-null score; cleanup was verified. The earlier fixed-control cleanup-audit failure remains in the evidence. These are developer controls, not independent LLM trials. Code-access comparisons, protected improvement experiments, portability and public release remain unqualified.

See [instructions](INSTRUCTIONS.md), [submission schema](SUBMISSION_SCHEMA.json), [data interface](DATA_INTERFACE.md), [scorer evidence](../../../authoring/reward-spacing-v1/scoring-runtime-v1/RESULTS.md), and [program evidence](../../../authoring/reward-spacing-v1/program-cli-v1/RESULTS.json).

Use `tools/neurobench.py score PAPER-FIND-044 --submission ...` for an existing answer, or `tools/neurobench.py run PAPER-FIND-044 --program ...` for a captured Python program. Both require a fresh `--output`, a current allocation through `--review`, and `--other-reserve-bytes`. Program execution exposes the original paper and data, accepts at most 64 KiB of source and a 2.5 MB JSON answer, and removes the producer before private grading. Neither command invokes an external model service.

This package relies on checksum-pinned local data and the cached scientific Docker image. A valid run has no minimum scientific-performance threshold; inspect all score families, coverage and consistency together.

A separate [paired information interface](../../../authoring/reward-spacing-v1/paired-program-cli-v1/RESULTS.md) has verified paper+data and paper+data+selected-author-code branches. Both share the same instructions, data, scorer and limits. Code availability has been tested; code use, LLM benefit and scientific improvement have not.
