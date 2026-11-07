# Run a NEURAL-017 fixed program

The existing package supports both finished prediction files and an independently qualified submitted-program path. This page supplements the frozen, earlier scorer-only README; it does not change that scorer or its qualification.

For an attempt, give the author the [candidate guide](../../../authoring/nlb-cosmoothing/local-release-v1/CANDIDATE.md), the existing [prediction contract](INSTRUCTIONS.md), [schema](public/schema.json), and [attribution](public/LICENSES.md). Do not give them the operator setup, assets manifest, previous solutions, private arrays or qualification results. The candidate process receives only the pinned public NPZ at execution.

From the repository root, the registered interface is:

```sh
python3 tools/neurobench.py run NEURAL-017 --program /absolute/program.py --output /absolute/repository/artifacts-build/FRESH_ATTEMPT --dry-run
```

Removing `--dry-run` executes training, prediction and grading. It does not start an LLM. This command currently embeds a historical 106,000,000-byte reservation for other work; it is safe to use for a new attempt only after the operator verifies that this covers all current other reservations and records a new attempt allowance. The unchanged direct wrapper supports an explicit current reservation; see [operator setup](../../../authoring/nlb-cosmoothing/local-release-v1/OPERATOR_SETUP.md).

The source is capped at 64 KiB; candidate execution is capped at 20 seconds. The candidate writes one `predictions.npz`. Capture, program termination, source/output commitments, private grading and cleanup are separate recorded steps. Valid predictions receive a continuous co-smoothing score and signed comparator difference, including negative differences. No acceptance threshold is added.

This is a local development task for one exposed macaque recording, with full-trial retrospective inputs. A clean workspace rehearsal for this particular package is proposed, not completed. The current host-specific Docker endpoint and unpublished image identifier prevent a claim of independent-machine installation. Neither this page nor a successful attempt promotes the task to a full study, public release, or general neuroscience capability benchmark.
