# Full-panel author-code replay entry point

This operator-only CLI calls the existing `program/author_replay.py` component for all 40 selected Figure 6B sessions and all 200 source-seeded fivefold BernoulliNB fits. It closes the missing command-line invocation and persistence interface. It is **not a completed benchmark run**: original data execution has not been performed to qualify this entry point.

Install this directory as `source-api-cli-v1` beside the existing `program` directory. Keep those existing scientific components unchanged. `DEPENDENCIES.json` and the CLI freeze their current bytes and SHA-256 values. The CLI captures and authenticates all five source bodies before compiling them; it does not accept a participant-selected implementation.

The selected question is retrospective binary avoidance versus escape. Use all 40 sessions, source seed 622, the original stratified fivefold assignments, source preprocessing and full per-session OOF probabilities. The source tie at 0.5 belongs to escape. The primary statistic is equal-session balanced accuracy. The inherited published reference is 0.7271; it has not been attained or reproduced in this delivery. Separate SVC code uses other evaluation procedures and must not replace the selected endpoint silently.

## Operator invocation

Run only after the benchmark owner selects the original operation and admits its inputs. The source files and diagnostics belong to the trusted operator. Do not expose private prepared paths, session mappings, labels, reference probabilities, diagnostics or output directories to participants.

```sh
python -B source-api-cli-v1/cli.py \
  --source-root program \
  --authority /operator/selected-authority.json \
  --authority-sha256 SELECTED_AUTHORITY_SHA256
```

The paths above are placeholders, not an executable selection. Use an already qualified interpreter and the existing adopted NumPy 2.2.6, SciPy 1.15.3 and scikit-learn 1.6.1 construction runtime. Existing metadata alone does not qualify loaded libraries or establish historical execution equivalence.

The exact JSON authority keys are:

- `schema`: `foraging_source_api_cli_authority_v1`; `task_id`: `PAPER-FIND-036`.
- `limits`: the existing common.Budget fields `read_bytes`, `write_bytes`, `retained_bytes`, `other_future_bytes`, `free_floor_bytes`, `wall_seconds`.
- `prepared`: ordinary-file descriptor with `path`, exact `bytes` and `sha256` for the full existing prepared manifest (at most 16 MiB).
- `author_source`: descriptor for the retained author script (8,776 bytes, SHA-256 `abfde10a70eec9a8f621909ec9fac37463efceb7bd5b5dbdb5eff37d6fcf4b63`).
- `output_root`: a new private directory; existing or partial outputs are refused.
- `output_numeric_capacity_bytes`: positive cumulative capacity for all 40 float64 vectors, computed from the admitted full manifest before fitting.
- `metadata_cap_bytes`: positive per-document cap at most 2 MiB.
- `component_scope_acknowledged`: exactly `true`.

The owner must reserve complete input, fit, output, filesystem-allocation and failure extents before running. The CLI reserves 8 KiB from selected write and retained limits for its single terminal diagnostic. Its counters cover explicit managed I/O, not Python imports, physical I/O, memory pressure or all outer-process activity. The owned outer runner must enforce the hard deadline, drain and bound stdout/stderr, retain failure evidence and close the complete child process group. The CLI itself supplies cooperative budget checks, not process isolation or hard RAM enforcement.

On component success, the new private directory contains exactly one raw little-endian float64 probability vector per session, `AUTHOR_COMPONENT.json` and a final `COMPONENT_RESULT.json` containing hashes and extents. All 40 arrays are validated before output creation. Persistence failure may leave partial files; those files are never a successful result and are not automatically resumed or overwritten. The terminal record is bounded and operator-only. Reported fit counts are preserved when the replay component supplies them; an unknown interruption remains unknown, not zero.

## Scientific limits

This entry point executes only the real author-API branch. It does not implement the original full shuffle companions, required model audit, independent reference qualification or protected paired participant execution. It does not qualify a whole historical author script or provide custodied evaluation. All paper reproduction and improvement decisions remain unset. The existing selected reproduction contract compares the complete per-session score vector and mean; reference probabilities are audit artifacts, not a new requirement that every candidate reproduce each pointwise probability or label.

The final benchmark must retain the paper+data and paper+data+official-code access arms, reproduction and improvement on the same selected task, original source shuffle companions and the existing paired candidate comparator. Native understanding of neural data is a different benchmark direction; this programme's internal `native-A/B` role labels do not establish that capability.

## Generated checks

```sh
python -B source-api-cli-v1/test_cli.py -v
```

The six tests use generated arrays and a stub replay object. They test complete all-40 export, missing last-session refusal, nonfinite output refusal, cumulative capacity, overwrite protection, honest failed-fit counts and bounded diagnostics. Two fresh subprocess probes verify rejection of tampered source before authority access and admission of all five unchanged pinned source modules up to an absent authority. These are software tests, not original scientific observations, numerical equivalence, a reference run or a paper win. Test-only `FORAGING_EXISTING_SOURCE_ROOT` can locate the unchanged `program` directory before integration.
