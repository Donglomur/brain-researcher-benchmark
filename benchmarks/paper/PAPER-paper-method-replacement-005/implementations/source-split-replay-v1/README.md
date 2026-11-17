# Source trial partition replay

This component computes the pinned NEDS preparation split from ordered, already-aligned original trial identities. It also checks those identities against an evaluator session and quantifies shared recording time between the resulting partitions. It addresses a gap in `initial-evaluator-v1`: disjoint user-supplied trial IDs do not establish the author's partition or physical time separation.

The source sets the global legacy NumPy seed to 42 **once per invocation**, then draws `np.random.choice(np.arange(n), n, replace=False)` for each session that reaches the partition block. Boundaries are the literal Python `int(0.7*n)` and `int(0.8*n)`. Replacing these with rounded proportions changes some sizes: at 90 trials the source gives 62/10/18, because the first floating product lies below 63. Resetting the seed per session also changes later session membership when preparation occurred in one process.

`source_split.py` uses a private legacy `RandomState`; it does not mutate NumPy's global RNG. It exports ordered indices, trial IDs, stimulus-aligned windows, and state hashes, and returns the final full state for continuation. A captured pre-split state is supported when earlier RNG draws cannot be reconstructed. No arrays, targets, method predictions, or models are loaded by replay.

Requires the existing Python and NumPy environment. It neither installs dependencies nor calls a service.

```sh
python3 source_split.py /external/operator/request.json /external/operator/replay.json
python3 source_split.py /external/operator/request.json /external/operator/replay.json \
  --verify-bundle /external/operator/matching-session-bundle.json
python3 -I -B test_source_split.py
python3 -I -B test_source_split.py --prepare-source /external/pinned/src__prepare_data.py
```

The ordinary suite has seven generated controls. Supplying the external author file adds a SHA-verified AST oracle: it executes only the four original partition assignments, compares three sequential generated sessions and the final RNG state, and performs no acquisition, preprocessing, or model execution. Use the project test pool for these commands during the parallel construction wave.

## Operator request

The closed request schema is:

```json
{
  "schema": "neds-source-split-request-v1",
  "source_commit": "61d2ef65556dbbc2b828d542f19bd4e7134c92f3",
  "evidence_kind": "operator_supplied_unqualified",
  "rng_origin": {"kind": "source_process_seed", "seed": 42},
  "events": [
    {
      "eid": "d23a44ef-1402-4ed7-97f5-47e9a7a504d9",
      "trial_ids": ["original-row-id-0", "original-row-id-1"],
      "stim_on_seconds": [10.0, 13.0]
    }
  ]
}
```

These two rows illustrate the schema only; they are not an observed source session. Actual requests and outputs belong outside Git. `evidence_kind` may instead be `generated_engineering`. Source IDs are read from the unchanged predecessor's 74/10 roster; unknown or repeated EIDs fail. The request contains only sessions that reached the source partition call, in their actual process order. Source skips before that call consume no partition draw and must not be inserted as zero-length events. Separate process invocations require separate requests. The operator must preserve their original grouping; the cohort's train/test roster order alone does not establish preparation order.

For an observed NumPy state immediately before the first split, use `rng_origin={"kind":"captured_pre_split_state","state":...}`. `encode_state(rng)` supplies the closed state representation: MT19937's 624 uint32 keys, position, Gaussian-cache flag and finite cached value. The final state can resume a sequential replay; the request digest binds the complete initial state. Replaying from seed 42 assumes no unrecorded random consumption after the source seed. Neither a declared state nor that assumption proves original execution history.

Trial IDs and times must follow the source's **post-alignment** row order. Do not sort them by time or redraw exclusions. Recovered trial identity must be joined to the original `stimOn_times`; array row numbers without that join are insufficient. This code does not select between paper 2-Hz and code >5-Hz units, correct list-truthiness validity masks, alter presplit scaling, or choose a camera. Those unresolved choices affect the eligible rows and retain their original qualification gates.

## Identity and time checks

`verify_partition_ids(report, evaluator_sessions)` requires exact matching session coverage and exact **ordered** trial IDs for all three partitions. It can check the corresponding session subset of the existing evaluator's bundle. It does not attest the bundle's arrays, unit order, or cohort completeness; those remain the existing evaluator's checks. It also does not authenticate a caller-supplied report. Pass a report freshly computed from the frozen operator request.

The overlap calculation uses source stimulus windows `[stimOn-0.5, stimOn+1.5)` seconds. For each split pair it reports overlapping pair count, affected trials on each side, a bounded list of examples, and summed pairwise overlap seconds. The sum counts shared time once per trial pair; it is **not** unique leaked recording duration. Merely touching endpoints do not overlap. The calculation preserves every row and split; purging overlap would create a different benchmark. The windows concern temporal support within a session, not animal independence or a causal leakage claim for every model.

This is a conditional source algorithm component, not recovered historical partitions or a qualified paper benchmark. No authentic trial identities, ONE objects, original RNG traces, animal joins, or source numerical results were supplied or processed in this revision. Full 74-session pretraining and ten-session held-out evaluation, nine endpoints, author calibration, source preprocessing resolution, observation masks, and joint improvement rules remain unchanged.
