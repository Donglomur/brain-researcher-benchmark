# Cardiac aperiodic slope: choose the intended route

2 November 2026. PAPER-ROOT-ADD-016 has a registered six-model program route and a separately qualified paired OLS/HC3 companion. They answer different numerical questions and are not interchangeable. The adjacent README and instructions are historical scoring documents referenced by source/evidence closures; this companion records current delivery without changing their bytes.

| Route | Candidate task and public inputs | Output and grade | Current delivery |
|---|---|---|---|
| Six Student-t models | [TASK](../../../authoring/cardiac-aperiodic-v1/program-completion-v1/public/TASK.md), [public allowlist](../../../authoring/cardiac-aperiodic-v1/program-completion-v1/registration/program_assets.json): the 655-person processed Salzburg CSV, model/schema/paper documents, declared helpers and offline wheels | Only `summary.json`, at most 200,000 bytes; all six models and five parameters per model. Continuous posterior-summary discrepancies, with self-reported diagnostics and Monte Carlo limitations. | Registered `tools/neurobench.py run PAPER-ROOT-ADD-016`; actual common-command qualification passed. |
| Paired OLS/HC3 sensitivity | [TASK](../../../authoring/cardiac-aperiodic-v1/paired-program-v1/public/TASK.md), [seven-file public map](../../../authoring/cardiac-aperiodic-v1/paired-program-v1/ASSETS.json): same CSV, paired contract/schema/provenance and paper documents; no statistical helpers or wheels | Only `summary.json`, at most 32,768 bytes; 13 quantities for retained-minus-rejected age association, full HC3 covariance and marginal-slope identity. Continuous errors, no accuracy floor. | Four fixed controls passed. **Not registered behind the common cardiac command.** The four-attempt capacity policy is exhausted; a new reviewed policy/grant is required before an ordinary paired attempt. |

Give a candidate only the chosen route's public allowlist. The paired `ASSETS.json` also contains operator/control descriptors: use its `public_inputs` subsection, not the entire file as a candidate packet. Neither this operator guide, the private reference, prior solutions nor the parent repository belongs in the candidate workspace. All 655 processed participants are exposed development data.

Both routes invoke the candidate as `python -I /program/program.py --input /input --out /output`, with 120 candidate seconds, 1.75 CPUs and 3 GiB. The six-model route also uses its declared offline dependency setup. Each whole operator attempt is 210 seconds with 8 MB durable reserve. These bounds are not new grants.

The registered **six-model** command can be inspected without dispatch:

```sh
python3 tools/neurobench.py run PAPER-ROOT-ADD-016 \
  --program /absolute/path/to/program.py \
  --output artifacts-build/fresh-cardiac-six-model-attempt \
  --review /absolute/repository/path/to/current-review.json \
  --other-reserve-bytes 102000000 --dry-run
```

The review must be an existing repository file and the output must be fresh. The reserve is an example minimum; the operator must bind current reservations, source/program pins and latest accounting before removing `--dry-run`. The current registered wrapper is `authoring/cardiac-aperiodic-v1/program-completion-v1/run_program.py`.

The executed paired wrapper is `authoring/cardiac-aperiodic-v1/paired-program-capacity-v2/run_program.py`, accepting `--program`, `--output`, `--review`, and `--other-reserve-bytes`. It has no dry-run option. Do not dispatch it using an old four-control review, substitute it into the common command, or treat its accepted controls as an ordinary-run grant. Its [qualification acceptance](../../../authoring/cardiac-aperiodic-v1/paired-program-capacity-v2/QUALIFICATION_ACCEPTANCE.json) and [completed results](../../../authoring/cardiac-aperiodic-v1/paired-program-capacity-v2/RESULTS.md) are the starting evidence for a future policy decision.

Both program routes retain the candidate summary at `<output>/unit/summary.json`, full grade at `<output>/score.json`, and lifecycle/cost at `<output>/outer_receipt.json`. The legacy `score PAPER-ROOT-ADD-016` command grades six-model summaries only; it does not execute a candidate or grade the paired companion. Never interpret a valid summary or a process exit as proof of correct inference.

The paired controls matched all 13 reference quantities; this was one developer reconstruction plus three interface controls, with no independent LLM trial. Its OLS/HC3 contrast is not a joint Student-t posterior contrast. The original project still requires the promised robustness/independent-cohort work and scientific interpretation; a matched paper-only/+code comparison is also unmeasured. Raw ICA/spectral preprocessing and full Cam-CAN reproduction were explicitly outside the original bounded Salzburg project and are not added as requirements here. No full-contract, research, release or new-ID promotion follows from these routes. See the [four-task guide](../../../docs/neuroscience-benchmarks/BOUNDED_LOCAL_TASKS.md).
