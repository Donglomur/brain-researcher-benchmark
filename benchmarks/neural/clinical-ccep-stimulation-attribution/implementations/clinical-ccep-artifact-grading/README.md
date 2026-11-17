# CCEP: complete primary prediction-artifact grading

This publishes the accepted V2 primary scorer and its V3 source-binding identity
for the existing `clinical-ccep-stimulation-attribution` task. It computes mean
block negative log probability within each patient, then weights all five
patients equally. Blocks retain every repetition; neither block counts nor
pulse counts increase a person's primary weight. This is original benchmark
software, not the authors' BPC implementation or a completed clinical benchmark.

`score.py` and `test_score.py` are unchanged accepted source. Python 3.11+ Unix
standard library is sufficient. [INTERFACE.md](INTERFACE.md) defines the full
policy, prediction and target schemas, floors, class order and coverage behavior.
No clinical inputs, private targets or authenticated anatomical mapping are supplied.

The trusted API is
`score_files(policy_path, expected_policy_sha256, submission_path, targets_path)`.
The operator supplies an independently frozen policy hash, never a candidate's
chosen hash. The policy pins the complete target body. Complete prediction
admission precedes opening targets. Source coverage gaps return no primary loss;
unsupported training classes remain reported without removing the held patient.

From this directory, use an operator-owned mode-0700 working directory and keep
the report and error stream private:

```sh
umask 077
set -C
python3 -I -S -B score.py \
  --policy OWNER_POLICY.json --expected-policy-sha256 OWNER_POLICY_SHA256 \
  --submission COMPLETE_PREDICTIONS.json --targets OWNER_TARGETS.json \
  > NEW_PRIVATE_REPORT.json
```

`set -C` prevents ordinary shell overwrite and `umask 077` restricts a newly
created report. A failure may leave the fresh report with a refusal record or
partial contents; preserve it. Exit 0 means the declared full roster was scored,
2 means invalid/incomplete input, and 3 means unresolved source coverage. These
statuses do not certify scientific provenance, biological completeness, actual
LOPO training, model competence or isolation. The API returns private reports;
the CLI prints them to stdout. The operator owns feedback and process custody.

This directory includes only the `original_full_scope` primary condition and
rejects transformed conditions. The adjacent [complete-block pairing component](../clinical-ccep-pairing/README.md)
supplies prospective mappings, packet materialization and support-matched paired
losses while retaining this primary score unchanged. Remaining work includes full
five-patient source/contact/block joins, clinical clocks and anatomy/mixed-pair
policy, legal exposure, competent train-only references, protected matched access,
authentic paired execution and uncertainty.
No registered count, historical contract or readiness flag changes here.

Run the new relocated interface checks, which use only invented fixtures:

```sh
python3 -I -S -B test_delivery.py
```

They verify local member identity, isolated real CLI behavior from an unrelated
working directory, and the public-artifact/private-target boundary in the relocated
module. The unchanged numerical test suite is retained, not replayed by this
command. Source manifests identify exact local files and accepted versions.
Project source is repository-MIT; this grants no rights over external clinical
data, publisher content or official MATLAB code.
