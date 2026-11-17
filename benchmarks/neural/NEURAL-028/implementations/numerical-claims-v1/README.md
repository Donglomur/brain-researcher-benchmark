# NEURAL-028 numerical investigation claims

This component checks a complete numerical investigation report against the original packet's measured arrays. It advances the missing submission-claim checker in the current [understanding contract](../../understanding.v1.json). The earlier [evaluator](../initial-evaluator-v1/README.md), original task, and historical files are unchanged.

It is an **operator numerical checker**, not a delivered participant access mode or a free-text understanding grader. It has no native data, participant sandbox, answer transport, or real solver result. A passing report means numerical agreement under the frozen estimator; it cannot establish direct interpretation, causal reasoning, authentic source coverage, or behavior-matched reward coding.

## What is checked

Every declared session and every session-local neuron must be present, including nonvisual neurons. Reports include matched and raw stimulus d-prime, the separate unmatched reward-location d-prime, all four cortical regions with their complete/undefined denominators, stimulus-specific retained frames and trials, common behavioral strata, and the moving-gray baseline companion. The reward split and its unmatched status remain explicit. Neuron indices identify the order within one session only; cross-session cell correspondence is never inferred.

The primary result includes session means within each animal/phase, paired after-minus-before changes, equal-animal regime means, frozen animal-bootstrap intervals, and supervised-minus-unsupervised changes. Both phase session lists and denominators remain visible when a phase is undefined. Absent regions, constant cells, incomplete estimates and singleton uncertainty remain `null`; null, negative and positive scientific outcomes are equally valid answers. The checker requires every section, so reporting only a favorable contrast or dropping an undefined region fails.

The calculation reuses the pinned, previously reviewed numerical evaluator rather than accepting precomputed truths from a submission. Its SHA-256 is checked before import:
`67777d97d6d00037efff66ff58774a49f4cd28b27b0ed018f79f77ae218e12d7`.
The original source revision is `ba64ac697f5d9914926baac79399e80707a5f3a6`; source definitions and acquisition limits remain in the predecessor's [provenance](../initial-evaluator-v1/source-provenance.json). No author code or native data is copied here.

## Report and operator interface

`claims.build_reference(packet)` returns the exact complete `neural028-numerical-claims/v1` report shape for operator construction/audit. **It is answer-bearing and must remain outside participant observations and public Git.** The operator must separately freeze a participant-facing schema/example built from generated data. The report binds the full canonical JSON packet and protocol hashes and has these mandatory sections:

| Section | Identity and quantity |
| --- | --- |
| `scope` | Conditional stimulus endpoint, calcium activity, source VR movement, mouse independence, session-local cells, unmatched reward |
| `common_support` | Complete common stratum IDs and equal stratum weighting |
| `sessions` | Object keyed by exact session ID; `neurons` keyed by decimal zero-based cell index, matched regional fractions, support counts and unmatched companions |
| `animals` | Object keyed by `mname`; regime, both complete session lists/counts, before/after/delta by region |
| `regimes_by_region` | All cortical areas; all supplied regimes, retained animal counts, undefined IDs, mean changes and intervals |
| `sup_minus_unsup_by_region` | All cortical areas; signed regime contrast and interval |

`claims.grade(packet, submission)` recomputes the reference from the original arrays. A well-formed wrong value yields an incorrect-claim path; missing or extra objects, unknown identities, malformed numbers and a different packet/protocol fail closed. Floating measurements use fixed absolute tolerance `1e-8` plus relative tolerance `1e-6` times the expected magnitude. Counts and scope labels are exact; booleans cannot serve as numbers. JSON duplicate keys and NaN/Infinity are rejected. The checker emits separate section counts and complete-correctness status, with no weighted leaderboard score or expected answer values in the scorecard. These counts are software diagnostics, not measures of neural understanding.

Use an existing Python/NumPy environment:

```sh
python3 claims.py --packet /operator/packet.json --submission /operator/report.json --output /operator/scorecard.json
```

The output must be a new file and cannot overwrite an input. Packet, report and scorecard remain operator-owned. The CLI does not export reference answers. The external runner must freeze submissions before scoring and withhold case-specific feedback; this standalone library is not a security boundary against a participant who can read the operator environment.

## Controls and limits

Task-local generated controls use analytically known stimulus effects, unequal session counts, a negative regime contrast, a null effect, constant decimal signals, absent regions, malformed reports and the CLI. They check equal-animal aggregation and verify the predecessor's bootstrap sequence without altering its seed/policy. These are software checks, not author inference, scientific replication, native preparation or participant performance. Run under the shared reviewed test pool in the current construction wave.

Native cohort/session mapping, source-array and interpolation authentication, amplitude comparability, behavior-matched reward, author/comparator execution and protected assessment remain open. This checker does not grade held-animal explanatory predictions or free-text reasoning. No access condition, scientific qualification or canonical admission status is changed.
