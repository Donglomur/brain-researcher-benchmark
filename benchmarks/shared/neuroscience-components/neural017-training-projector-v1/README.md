# NEURAL-017 training-only byte projector

This operator library constructs a training-only archive from an independently authenticated complete NEURAL-017 public packet. It copies eight NPY member byte streams without decoding numerical arrays. It has no command-line projection entry point. The [existing NEURAL-017 scientific source](../../neural-017/README.md) and [adaptive broker](../neural017-adaptive-broker-v1/README.md) retain their separate responsibilities.

The output contains exactly these members, in this order:

```text
train_counts_heldin.npy
train_counts_heldout.npy
train_trial_ids.npy
heldin_unit_ids.npy
heldout_unit_ids.npy
train_condition_ids.npy
bin_left_edges_ms.npy
source_manifest_sha256.npy
```

Training counts for held-out units are legitimate supervised training data. Evaluation counts, evaluation trial and condition identifiers, evaluation mask and panel fingerprint are excluded. A successful projection verifies all 13 source members, including the five discarded members, for CRC and NPY magic/version. Selected uncompressed bytes are copied verbatim into a deterministic stored ZIP with fixed metadata.

## Operator boundary

Call `derive_training_packet` with an independently authorized exact source size/SHA256, a new destination and an absolute monotonic deadline. Source authentication precedes ZIP parsing. The corrected pre-parse guard rejects ZIP64 end-directory locators before Python's ZIP parser can replace the bounded classic directory fields; local-member ZIP64 sizes remain supported.

Use trusted operator-owned directories on a filesystem supporting the required POSIX file, hard-link and directory-sync operations. The source must be an ordinary single-link file, with no symlink ancestors. An existing destination is preserved. Successful publication uses a mode-0600 temporary file, atomic no-overwrite linking and directory synchronization. Failure cleanup and identity checks support this trusted-directory model; they are not a hostile-host filesystem sandbox.

The complete receipt and errors must stay operator-side: they expose full-source identities, paths and accounting that depends on discarded evaluation members. `verified_members` is integer 13; `members` contains eight ordered member pins. Candidate training requests receive only the projected training view, including after controller commitment. Lifecycle phase alone must not determine which view is exposed.

Input and output caps are each 128,000,000 bytes; total expanded member bytes are capped at 128,000,000 and cumulative source-stream reads at 256,262,144. The source calls for a prospective 384 MiB managed source/decode reservation, 128,000,000 retained output bytes and a scratch inode. Deadline checks are cooperative. An outer owner must provide admission, a hard process deadline and recovery for blocked system calls or process termination.

NPY magic/version and ZIP checks do not establish array shape, dtype, pickle safety, biological provenance or split validity. An accepted scientific schema validator remains necessary. Authentic projection is unrun; this package supplies no numerical validation, qualified transport/backend, execution authority or scientific result.

## Existing controls

From the repository root, using Python 3.11.18:

```sh
python -I -S -B -m unittest discover -s benchmarks/neuroscience/components/neural017-training-projector-v1 -p 'test_*.py' -v
```

There are 18 existing invented controls: 17 author tests and one independently authored ZIP64 pre-parse regression. They use temporary invented archives and no authentic neural arrays or NumPy. The accepted corrected implementation previously passed those controls. For this public layout, the independent test changes only its source-file lookup to a sibling path; every adversarial assertion and the exact implementation byte/SHA check remain unchanged.

Assembly did not execute the tests or the adapted regression. The appended CI job is configured to authenticate all five component files and run all 18 controls; its outcome must be assessed from the exact future run. [PROVENANCE.json](PROVENANCE.json) records the frozen identities and the single portability transformation. No benchmark catalog, count, scientific metric or qualification status changes.
