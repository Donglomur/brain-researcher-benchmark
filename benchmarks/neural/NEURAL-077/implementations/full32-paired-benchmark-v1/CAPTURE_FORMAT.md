# External paired capture format

This package verifies completed captures offline. It does not ship a participant executor or establish process/provider isolation. File hashes and required closure fields verify the committed records; they cannot prove that an untrusted producer recorded real execution.

Before query access, use evaluator.py freeze to capture each complete declared Python/config bundle. Pin both FROZEN files and bundle identities in one selected contract. Preserve the information policy, exposure declaration and external interpreter/clock descriptors. The contract must bind this package's SOURCE_BINDINGS.json and evaluator.py identities. The supplied template remains unselected until an operator supplies its real external operands.

For each of the two conditions, preserve FROZEN.json and the exact reconstructed CLIENT.py. Retain 6,400 episode directories named 0000 through 6399 in the authenticated session's sorted opaque trial-ID order. Each directory contains:

- INPUT.bin: four-byte network-order length plus the exact complete prompt, including all four demonstrations and the complete query.
- OUTPUT.bin: one complete length-prefixed original first response.
- END.json: schema erp-full6400-owned-episode-v1, status ok, exact trial_id and condition, returncode 0, pid > 1; owned_cleanup uses that same pid and sets cleanup_complete, reaped and group_absence_observed true. stdout_EOF_observed and normal_exit_observed are true; generated_protocol_only is false. The record binds exact input/output byte counts and SHA-256 values and context_sha256.

These custody fields are requirements on the trusted external producer. Synthetic records from source tests do not qualify a real run.

The first-attempt JSONL envelope supplied to consumer.py collect is:

```json
{"trial_id":"OPAQUE_TRIAL_ID","condition":"numeric_direct_four_demo","context_sha256":"EXACT_PROMPT_SHA256","status":"ok","response":"{\"trial_id\":\"OPAQUE_TRIAL_ID\",\"target_probability\":0.5}","error":null}
```

Use the corresponding exact condition ID for the program arm. The response string must contain only trial_id and target_probability; no boolean, nonfinite or out-of-range probability is accepted. Preserve the original first response. The collector retains attempts.jsonl, writes sorted predictions.jsonl only after all 6,400 unique successes, and produces COMPLETE.json or FAILED.json. It never scores or certifies isolation.

Place the successful collection under collection/. ARM.json must use schema erp-full6400-numeric-arm-v1 and status closed_unscored_arm. It binds condition, the selected contract pin, source_bindings pin, public_manifest pin, bundle_identity, query_count 6400, attempt_inventory_count 6400, private_target_reads 0 and scoring_performed false. It pins collection/COMPLETE.json and collection/predictions.jsonl. Its episodes array has exactly 6,400 ordered rows, each containing trial_id, status ok, and end with the END.json byte count and SHA-256.

The public-arms JSON maps each exact condition ID to {root, receipt:{bytes,sha256}}. The private-material JSON is {root, complete:{bytes,sha256}}, identifying the builder's COMPLETE.json and private join. Evaluation does not open this private descriptor until both public arms pass all verification. Private material must join exactly the 32 fixed participants and 6,400 unique public queries, with 40 targets and 160 standards per participant.

The consumer permits at most 262,144 UTF-8 context bytes. Evaluation requires a complete retained prompt of at most 196,608 bytes and response of at most 4,096 bytes; a collection envelope is at most 16,384 bytes. Do not truncate or substitute content. Evaluation rejects incomplete frames and mismatched content, IDs, bundles, manifests, contracts, sources, episode counts or custody records.

See evaluator.py and consumer.py for the executable validation rules. Successful offline verification is conditional on trusted external capture and private-material provenance; it is not an execution, sandbox or scientific qualification claim.
