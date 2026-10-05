# TIMEDECODE-001: within-recording modality-decoding method control

## Scientific target and paper relationship

Use the original MNE sample audiovisual recording for an explicit comparison of
pooled-time and separately fitted per-time logistic classifiers under one fixed
held-out-trial split. This is an **easy computational method control**, not an
un-cued trap, an independently validated neural finding or a demonstrated hard
task. Its fixed recipe is public.

[Gramfort et al.2013](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2013.00267/full)
§3.3/Figure8/Table3 illustrates left-ear versus left-field, separately fitted
per-time linear SVC with repeated ShuffleSplit. This task changes laterality,
classifier and cross-validation, and adds a pooled-time estimator. It does not
reproduce Figure8's numerical curve.
[King & Dehaene2014](https://doi.org/10.1016/j.tics.2014.01.002) motivates held-out
trial temporal decoding; pooling times is not their cross-time generalization
matrix. A match between a per-time curve and a reference cannot attest that a
different pooled classifier used the right split or source.

## Data and scope

The version6 original MNE OSF archive is identified by published MD5 and SHA256.
Only its filtered raw FIF, supplied event FIF and version marker are staged;
selected source bytes are65,733,932. Build-time retrieval is bounded and checked;
agent/oracle/verifier runtime is offline. Inputs are recorded data, not synthetic
subjects. Unit-test fixtures and deliberately wrong outputs are test controls,
not substitute scientific input.

No unrestricted dataset license was established: source documentation permits
familiarization use and excludes evaluating MEG/MRI hardware performance. Code
licensing is not recording licensing. Do not publish data-containing images
without resolving the grant.

Source header evidence gives150.15374755859375Hz and40Hz low-pass. The old decim2
step had Nyquist37.5384Hz and did not add an anti-alias filter; it is removed,
without changing the released filtering. Original source SSP vectors have no
selected-grad columns. Full-rate rejection and all output grids are regenerated,
not forced to match the historical30-point bank.

The scientific unit is one person/recording. Candidate event metadata includes
149 adjacent full-epoch overlaps and71 prior-analysis/next-baseline overlaps;
laterality/modality order is structured. Whole-trial folds prevent direct reuse
of the same trial's rows, but do not imply all source samples are independent or
all preprocessing is fold-local. The conditional estimate is not new-person,
new-session, unseen-latency, cognitive-onset or universally leakage-free evidence.

## Public method and grading

`environment/method_contract.json` freezes source-clock epoch construction,
full-rate PTP rejection, identical chronological trial-level SKF5seed42 mapping,
train-only scaling, the C1 logistic objective and finite/stationary convergence.
Both models' complete signed OOF predictions bind to original event/time/fold
identities. The verifier recomputes all fold/time/headline summaries from those
predictions; it does not infer grouping from a low accuracy band or expected gap.
Pooled mean-fold accuracy and all-OOF accuracy remain separate quantities.

Source epochs, scalp channel identity, sampling and support metadata are checked.
Reference construction reparses original source files and independently fits
the public objective. Genuine independent implementations and harmless output
reordering/rounding/extras must pass; wrong original identities, coherent invented
predictions, source or method changes, incomplete grids and summary mistakes fail.
No correlation-only grading, forced above-chance outcome, nonconstant-table rule,
performance-gap sign or prose-keyword condition remains. Partial outputs do not
earn promised proportional credit: the documented reward is all-or-nothing.

## Evidence and limits

See `REPAIR_STATUS.md` for the actual execution tier. Source authentication,
source-free engineering tests, original-data native execution, independent
numerical checks, final container oracle reward and model calibration are
separate gates. No historical score or author-reported pass is treated as a fresh
measurement. No Sol/frontier run or hardness claim is part of this repair.
Public reference artifacts remain susceptible to copying/contamination; numeric
agreement is not cryptographic proof that an agent executed the analysis.
