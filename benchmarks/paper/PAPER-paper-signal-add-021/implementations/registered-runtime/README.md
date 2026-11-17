# TMS behavioral summary reconstruction

**PAPER-paper-signal-add-021 — verified local scorer and program runner.** Reconstruct the released processed-table behavioral result using 135 participant-condition cells, nine equal-participant summaries and explicitly named paired contrasts. See [INSTRUCTIONS.md](INSTRUCTIONS.md) and [PUBLIC_CONTRACT.json](PUBLIC_CONTRACT.json).

The summary scorer passed 20 controls, including valid alternatives and null results, 19 generated arithmetic/schema checks, eight boundary checks and actual interruption recovery. The program stage then passed six authored controls: original, transformed and analytic inputs; stale answers; absent output; and coherent null output. Separate ordinary-program and actual shared-CLI runs passed with the positive and null programs. All resources were removed. These are construction and numerical controls; no LLM or paper/code-access experiment was run.

For a completed numerical submission:

```sh
python3 tools/neurobench.py score PAPER-paper-signal-add-021 \
  --submission /absolute/path/submission.json \
  --output "$PWD/artifacts-build/tms-submission-001" \
  --review /absolute/path/to/exact/root-review.json \
  --other-reserve-bytes 102000000
```

For a supplied Python program:

```sh
python3 tools/neurobench.py run PAPER-paper-signal-add-021 \
  --program /absolute/path/program.py \
  --output "$PWD/artifacts-build/tms-program-new-attempt" \
  --review /absolute/path/to/fresh/root-review.json \
  --other-reserve-bytes 102000000
```

The review binds the exact source freeze, program, fresh output path, latest charge, current storage reserves and a separately allocated 30-second attempt. Update the reserve value to the actual outstanding reservations. The completed integration allowances are consumed; future attempts need a fresh reviewed amendment. This is an operator execution grant, not scientific approval. Ordinary file scoring and program execution have each been exercised through the common CLI.

The scorer runs in the existing offline nonroot Docker image with six exact read-only file mounts, one CPU, 256 MiB memory and bounded scratch/output. It requires the pinned authoring/shared-runtime files in this workspace. Public table assets are referenced lazily; private saved reports and operator fixtures are excluded from candidate inputs. External redistribution rights and general host portability remain unresolved.

The [scorer results](../../../authoring/v1-tms-memory-v1/scoring-adapter-v1/RESULTS.md) and [program integration results](../../../authoring/v1-tms-memory-v1/program-cli-v1/RESULTS.md) preserve the controls and limitations. Valid inaccurate output is scored; all errors remain separate. There is no composite scientific-success score or significance reward. Raw gaze, historical inference and whole-paper qualification remain unresolved.
