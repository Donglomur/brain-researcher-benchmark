# Native behavior truth issuance

`behavior_truth.py:grade` closes a concrete evaluator gap: the existing native
Pearson scorer accepted arbitrary target packets from an operator callback.
This component instead captures the full original speed, phi and th NPY streams,
checks their bytes, hashes, shape and clock against the selected recording, and
constructs each target from the exact released `NFDataloader` target methods.
All candidate scalar packets are admitted before any target file or numerical
runtime is opened. Targets are consumed internally and are absent from the
returned score report.

The operator passes `grade(packets, request, array_root)`. `packets` uses the
existing `run_metrics.freeze_behavior_packets` format. The request contains:

- `schema: neuroformer_behavior_truth_v1`;
- `study`: a relative path, byte count and SHA-256 for the externally frozen
  study; its content and scientific adequacy require independent review;
- `recordings`: recording identity mapped to `cohort`, `recording_ticks`,
  `assets` and `provenance`. Every recording includes the full original speed,
  phi and th stream descriptors, with relative path, bytes, SHA-256, dtype and
  shape. Provenance is an external file descriptor. Its content must establish
  acquisition, clocks, units and original run mapping; a matching hash alone
  does not establish these facts;
- `cells`: exact original `case_id`, native `condition`, and the full ordered
  train/selection/evaluation support in the existing run-composition format;
- `limits`: positive `max_input_bytes`, `max_file_bytes`, `max_rows` and
  `max_values`. These bound capture and materialization; they are not measured
  RSS or authorization for native work.

`test_behavior_truth.py:fixture` supplies a complete **generated-data** request
example. It is not an empirical input or a source-study protocol.

Only original native continuous cells are admitted. Speed regression remains
speed alone; the joint cell retains speed, phi and th separately. The selected
recording must match the original cell's medial/lateral cohort. Complete source
arrays, full row order, recording extent, historical test-selection identity and
protected context separation are checked. No new split is generated. The
historical scorer retains its first 200 rows; the protected scorer retains all
rows. Protected conditions remain explicitly source-amended. No 5 ms bridge,
classification quantizer, neural-generation metric or new gaze convention is
substituted.

Source target extraction uses the effective original `round_n`,
`get_frame_idx`, `get_var`, `pad_tensor`, `NFDataloader.calc_intervals` and
`NFDataloader.get_behavior` definitions from author revision
`36ed94084628c253098d448048c980d3dea0050d`. Their containing source file is
SHA-256 `71ec03aa43aa911c53d680d9f7a8e0f9fd677f50f97ab983acccfcd63ffa15e4`.
The final `value[:, -1]` target selection follows the original `__getitem__`.
The existing pinned factory loads all predecessor sources into private module
namespaces; this component does not replace their import machinery or alter
any predecessor source.

The original source converts behavioral values to float32. A flat stream's
first window has an empty source slice and can be padded to zero. This is
retained and identified in the receipt. A column-shaped stream at that boundary
can trigger the original assertion; the issuer retains the failure instead of
flattening the array, skipping the row or inventing a value. No physical unit
or interpretation of that padded value is inferred.

Generated controls compare issued targets against the **actual original
`NFDataloader.__getitem__`**, with inert neural leaves, across all three heads,
float32 conversion and both flat/column layouts. They also check unchanged
first-200/full-support Pearson, corrupted input bytes, cohort mismatch,
protected context overlap, unsupported classification, and rejection of all
invalid candidate packets before target access. The checks import the existing
NumPy, PyTorch and SciPy for small generated arrays only. Run them through the
shared two-slot test pool; direct native execution is not authorized by this
README.

Original-paper reproduction and improvement are separate first-class outcomes.
This issuer supports their future source-bound scoring, while the historical
workflow and source-amended protected profile remain separately labeled. It
does not confer either outcome and does not assemble the paired paper+data
versus paper+data+author-code participant delivery.

This is an executable source component, not a qualified benchmark or an
original-paper result. No authentic observations, private historical answers,
weights or predictions were read to construct it. Original source/run/split
authentication, physical evaluator isolation, data rights, reference calibration,
the paper-version discrepancy, candidate runs and uncertainty remain unresolved.
The full 46-slot/85-condition/seven-family assignment remains intact. Integration
into the canonical operator is a separate owner action; this addition does not
activate or change registration.

Primary source: [author data utilities at the pinned revision](https://github.com/a-antoniades/Neuroformer/blob/36ed94084628c253098d448048c980d3dea0050d/neuroformer/data_utils.py).
