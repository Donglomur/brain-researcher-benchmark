# Original-trial support preflight

This operator-only helper addresses an unimplemented feasibility gate in the
NEURAL-042 prospective PAC task. It reads the complete 44-session / 36-person
**trial metadata**, not LFP, spikes, PAC estimates or participant answers. It
does not execute or replace the existing preparation, estimators or scorer.

The primary score needs both load and correctness endpoints. Each channel needs
at least ten pairs in each comparison; correctness needs ten pairs at each load.
Within each original-order quartile (`row0 // 35`) and probe-membership stratum,
the count-only maximum is `min(n_A, n_B)`. Summing those maxima gives an exact
count-only cardinality and an upper bound on nuisance-matched cardinality.
Artifact removal, channel exclusions and nuisance calipers cannot increase it.
Twenty total errors are therefore not sufficient: errors may fall in only one
load or in strata without correct trials.

The helper reports whether an endpoint is **not ruled out**, never that support
has been established. If no source person has any session passing one endpoint's
necessary bound, the primary cannot be scored under the existing rules,
conditional on authenticated metadata. A passing bound leaves clinical
eligibility, exclusions, matching, numerical support and R1/R2 agreement open.
No minimum is lowered, no sessions are pooled to manufacture pairs, and no
accuracy endpoint is replaced by reaction time. The existing T0 route still
uses numerical tools; this helper supplies no direct/native understanding task.

Input schema `neural042_original_trial_metadata_v1` has exactly:

- `schema`, `source_roster_sha256`, `sessions`.
- Each of all 44 sessions: `asset_id`, `source_sha256`, `subject_id`, `loads`,
  `correct`, `probe`. The three lists each retain all 140 original trial rows,
  in their original order, using literal integer codes (1/3, 0/1, 0/1).

The frozen source roster is the existing
`../programme-source/implementation-v1/preparation/SOURCE_ASSETS.json`
(16,501 bytes, SHA256 `988b0b979d9d940963ee8c0223b2e0941ef8754279f59f60afb459da91dbe548`).
Original NWB fields are `intervals/trials/loads`, `response_accuracy` and
`probe_in_out`, as specified by the existing preparation. **No extraction or
authentic metadata run has been performed for this addition.** A qualified
operator must establish source identity and correct metadata extraction. Hash
strings in the input and a matching metadata file digest are not that proof.
Input is capped at 1 MiB and existing outputs are never overwritten.
The saved CLI report retains the exact input metadata byte count and SHA256 in
`metadata_input`, so the evaluated export can be identified without recording
its filesystem path. This descriptor is an integrity binding, not extraction
authentication.

Run, once an authentic metadata export and its frozen identity are available:

```sh
python3 support.py --source-roster /operator/SOURCE_ASSETS.json \
  --metadata /operator/original_trial_metadata.json \
  --metadata-sha256 OPERATOR_FROZEN_SHA256 --output /operator/support_bounds.json
```

The complete output is operator-private because it retains source identifiers.
Its `summary` is an identifier-free aggregate, with explicit conditional and
unqualified status; selecting any public release remains an operator decision.
This package is not connected to automatic admission or the canonical scorer.

Semantic anchors are the existing `DESIGN.md` accuracy-feasibility gate,
`references/r2/matching.py::select_pairs`, `preparation/prepare.py` trial fields,
and `program/contracts.py` patient-level support. These define a prospective
measurement-reconstruction benchmark, not source-exact paper PAC reproduction.

For maintained generated checks after integration:

```sh
python3 -m unittest discover -s benchmarks/neural/NEURAL-042/implementations/trial-support-preflight-v1/tests -p 'test_*.py'
```

This is a proposed task component and test command. Actual CI enrollment is
owned by the repository integrator; local tests do not imply enrolled CI.
