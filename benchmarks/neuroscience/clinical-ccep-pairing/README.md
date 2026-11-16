# CCEP: complete-block pairing and matched losses

This is the prospective pairing extension for the existing
`clinical-ccep-stimulation-attribution` task. It supplies deterministic
whole-block maps, normalized paired packet materialization and matched
candidate/reference diagnostics. The complete original five-person score still
comes from the unchanged [primary component](../clinical-ccep-artifact-grading/README.md).

Keep these adjacent directories together:

```text
benchmarks/neuroscience/
  clinical-ccep-artifact-grading/score.py
  clinical-ccep-pairing/pairing.py
```

Python 3.11+ on Unix and the standard library suffice. The primary body must be
exactly 14,609 bytes with SHA-256
`2426ddc5585a113fb839e3b3dd78bf2c684d3f0d5fef2dac0b9af4ab1ebd6f32`.
The pairing loader verifies those bytes before executing the captured source.
Its relative lookup is the only production change from the accepted V2 pairing
source. The full generated pairing suite is retained unchanged.

[INTERFACE.md](INTERFACE.md) specifies every control-policy, full-block envelope,
prediction artifact and output field, along with the mapping proof, equations
and unsupported-support behavior. An operator must independently provide and
freeze the complete original policy, control policy, anatomical targets,
normalized full-block packets, matched reference roster and provenance evidence.
These are not supplied or generated from public placeholders. The package
contains no native data loader or acquisition command.

All five original people and every original case remain in the natural score.
The diagnostic moves entire response blocks within exact compatible strata;
recipient context and layout remain fixed. It keeps unsupported cases visible.
It averages paired losses over matching supported cases within each person,
then equally over supported people and distinct maps. Deduplicated maps are
not biological replicates. The prospective hash-ordered rotation family is
not uniform over every admissible permutation and provides no permutation
p-value or causal conclusion.

From this directory, use an operator-owned mode-0700 directory and fresh output
names. All hashes and private input locations below come from the operator:

```sh
umask 077
set -C
python3 -I -S -B pairing.py maps --policy POLICY.json --policy-sha256 POLICY_SHA256 --control CONTROL.json --control-sha256 CONTROL_SHA256 > NEW_PRIVATE_MAP.json
python3 -I -S -B pairing.py packet --policy POLICY.json --policy-sha256 POLICY_SHA256 --control CONTROL.json --control-sha256 CONTROL_SHA256 --map NEW_PRIVATE_MAP.json --map-sha256 MAP_SHA256 --transform-id TRANSFORM_ID --recipient-id CASE_ID --recipient-packet RECIPIENT.json --donor-packet PRIVATE_DONOR.json > NEW_PAIRED_PACKET.json
python3 -I -S -B pairing.py score --policy POLICY.json --policy-sha256 POLICY_SHA256 --control CONTROL.json --control-sha256 CONTROL_SHA256 --map NEW_PRIVATE_MAP.json --map-sha256 MAP_SHA256 --artifact ALL_ARMS.json --targets PRIVATE_TARGETS.json > NEW_PRIVATE_REPORT.json
```

Freeze the exact emitted map bytes and hash, including its newline, before arm
predictions. Materialize every supported case for every distinct map; every arm
must receive the same packet bytes. The packet command is a complete per-case
operation, not an authentic cohort producer or a process-isolation mechanism.
Map files, donor selection, policies, targets, reports and error streams remain
evaluator-private. Only authenticated paired input packets may be exposed to
participants after privacy review. Shell no-clobber and umask constrain new
outputs; preserve refusal/partial files rather than overwriting them.

Exit 0 denotes a successful declared interface operation, 2 invalid/incomplete
inputs, and 3 an unavailable null or unresolved original construction. No exit
code establishes authentic source equivalence, actual matched execution,
reference competence, protection, clinical generalization or scientific readiness.
Oversized complete outputs are refused, never trimmed.

Run only the new source-relocation checks:

```sh
python3 -I -S -B test_delivery.py
```

They use invented fixtures and verify the complete public member set, the
isolated three-command route, dependency identity and pre-target rejection.
They do not invoke the retained 20-method numerical suite. That full suite
remains available as `python3 -B -m unittest -v test_pairing` for future changes.

No data, answer values, private identities, official source, private integration
records or historical raw tool receipts are distributed. Code and generated
controls are original repository-MIT software. External clinical data, publisher
content and official-code rights remain separate. This adds source behavior to
one existing task; it does not increase benchmark or readiness counts.
