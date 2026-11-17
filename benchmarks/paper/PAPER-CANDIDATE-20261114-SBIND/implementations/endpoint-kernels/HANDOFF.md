# Frozen endpoint-kernel handoff

The independently authored implementation adds per-output MSE, four-channel
binary F1 and final-state fUS trial accuracy. Identity joins reject omitted,
additional and repeated predictions; brain masks stay explicit; no fold or
session aggregation is invented. Original task and improvement-contract files,
the prior whole-trial/normalization implementations and historical evidence are
unchanged. `SOURCE.json` pins every file in this new component.

The source bodies listed in `PROVENANCE.json` were read from retained external
primary captures and authenticated against both SHA256 receipts and Git blob
identities. No source payload was fetched. The inherited contract supplies the
full original panel and endpoint context; the full paper was not reacquired.

**Validation state:** all eight generated test methods passed in shared-pool
run `paper01-sbind-endpoint-04`, child exit zero. The three earlier attempts were
busy and launched no tests. The run used standard-library Python,
`-I -B test_endpoint_kernels.py`, through the verified default shared pool with
one thread, a 1 GiB RAM declaration and 180-second maximum deadline. Recorded
child CPU was 0.063138 seconds and peak RSS 27,197,440 bytes; the pool's memory
scope is maximum child RSS, not simultaneous process-tree memory. Sanitized
receipt identities and measurements are in `VALIDATION.json`.
Tests exercise hand-counted metric values, complete
generated 128×128 fields, output widths, row-identity failures, trial endpoints
and malformed operands. No scientific workload is included.

Independent review should check the mathematical metric definitions against
the pinned author source and confirm that no unknown table weighting or original
fold assignment was substituted. Pay particular attention to binary positive-class F1 versus
accuracy/micro-F1, one trial per fUS evaluation row, and the absence of implicit
prediction filtering. The final-state offset checks only declared metadata;
it cannot authenticate a model's actual information use.

Costs: zero downloaded bytes, zero authentic numerical preparation, zero author
inference/training, zero candidate/model trials, one generated suite execution
as of this freeze. Routine source/metadata reads were not independently metered.

Qualification is **source-inspected implementation with generated controls**.
Exact source identities, full original folds/masks, normalization/class mapping,
complete source panel execution, author calibration, aggregation and a valid
joint improvement rule are still needed. No full benchmark, paper reproduction,
improvement, current SOTA or new task count is claimed. Integration and canonical
registration/CI changes remain with their assigned owners.
