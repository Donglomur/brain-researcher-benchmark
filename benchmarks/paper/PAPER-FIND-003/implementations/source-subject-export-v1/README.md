# Original Learn-R subject-stage export

This component extends the original pre-outlier channel Learn-R boundary through
the author's subject/behavior table construction. It contains an actual MATLAB
producer and a Python checker for its exported rows. It does not reproduce the
downstream behavioral R regression or decide paper reproduction/improvement.

The complete `Ripple_offline_learning.m` at revision
`f143b0b7dca77bf9b09d5c7f39352fc5332c83c0` was obtained through one separately
selected GitHub Contents API request. The decoded 15,136 bytes have SHA256
`15969cc29b6d7d28d4d4700a044454092149b688c6af9c552314a8cbff2ce6bc` and framed
Git blob SHA1 `4fa42a59e67681d1a5e241041cf8aa422e8ecbf9`, matching that response.
This is fixed-ref API evidence, not an independently acquired commit/tree chain.
The earlier raw-host TLS failure remains preserved in private evidence.

## Native boundary

Call `[packet, subjLearnR] = export_subject_stage(T3, dtSubjACC, input_identity)`
in the intended MATLAB environment. `T3` is the original `groupsummary` table
from caller lines74–75, before outliers. `dtSubjACC` is the native performance
table read at line7. This function does not create those inputs, use the Python
learner's subject labels, or establish their original-cohort authenticity.

The original lines78–101 remain MATLAB operations:

- For each of stimulus, feedback and interval, run `rmoutliers` with method
  `mean` and `ThresholdFactor` 3. Replace flagged values with NaN; retain rows.
- Remove GroupCount before `unstack`; derive subjects by
  `regexprep(channel,'.*_','')`; use `grpstats(...,@nanmean)` and preserve its
  GroupCount. The original historical runtime/defaults remain unqualified.
- Perform the stable intersection, select its `ib` subject rows and require
  `ia == (1:height(dtSubjACC))'`. Extra learned subjects are allowed. Assign
  `testBeforeInfer` and `testBeforeMemory` in original performance-row order.

Additional lines only validate the supported input representation or observe
row identities, masks, native values and table metadata. They do not select
outliers, calculate subject means in Python, or add a regression.

The adapter supports exact ordered T3 columns
`channel, phase, GroupCount, fun1_trial_ripple`, unique channel×phase groups,
nonempty bounded text identities, and scalar real double values. It requires
all three phase labels somewhere in T3. This is an explicit adapter precondition,
not a claim that the author code synthesizes an entirely absent phase. Missing
individual channel-phase cells follow native `unstack` and are retained as NaN.
Tables with categorical/numeric IDs or missing/empty identities are outside this
version's supported domain; no coercion is used to merge them.

`input_identity` has the fields `learnr_input_sha256` and
`performance_input_sha256`, each a lowercase SHA256 declaration supplied by the
caller. Neither these strings nor `which`/`version` runtime strings authenticate
files, execution, the T3 derivation, historical MATLAB, or the cohort.

## Export and validation

`packet` is suitable for `jsonencode`. Cell arrays preserve singleton row lists.
The native output retains each stage's row order, table column order/classes and
row names. Nonfinite numbers use explicit `nan`, `positive_infinity` and
`negative_infinity` states; finite values have a numeric `value`. Metadata and
counts are declared native observations, not proofs of execution.

`python3 -I -S -B validate_export.py packet.json` checks original row indices,
channel/phase support, outlier-to-NaN transport, unchanged unflagged values,
suffix-derived subject mapping, unstack cells, complete subject/performance
joins and behavior assignments. It preserves native subject values without
recomputing or judging them. GroupCount values are retained and representation
checked; historical `grpstats` behavior is not independently certified.

The checker returns explicit `not_evaluated` numeric correctness and false
reproduction/improvement qualifications. A self-consistent fabricated packet
can pass these checks. A trusted native execution and original-input custody
are required before using it as scientific evidence.

## Controls and remaining work

The generated Python controls cover support/identity failures, masks, missing
cells, subject joins, nonfinite transport and malformed JSON. They run neither
MATLAB nor authentic data and do not validate native numeric parity. The earlier
14-test pre-outlier learner suite is not repeated.

The original caller invokes `R_scripts/LearnR_predict_performance.R` at lines106–107.
That producer and its execution/result identities are outside this component.
Authentic upstream T3/performance data, original runtime qualification, cohort
and trial-count controls, complete figure crosswalk, reference values/tolerances
and a justified same-task improvement criterion remain separate requirements.
No task, scorer, authority binding, registration count or readiness label changes.
