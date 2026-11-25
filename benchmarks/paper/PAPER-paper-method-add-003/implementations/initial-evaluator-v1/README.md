# Human LFP alignment evaluator

Construction package for `PAPER-paper-method-add-003`: loads content-pinned raw SpikeGLX LFP segments, computes an independent rigid registration control, and compares supplied default-DREDge/alternate displacement outputs against fixed/no correction using shared interpolation, reserved evaluation channels and a prospective consistency/fidelity panel. Cohort summaries require Pt01, Pt02 and Pt03.

Dependencies: Python 3.11, NumPy and SciPy. Run these commands in an existing environment with those dependencies available. The actual validation interpreter and versions are retained in external construction evidence.

From this directory:

```sh
python3.11 -m unittest discover -s tests -v
python3.11 evaluator.py protocol.json results.json
```

The protocol provides explicit raw-file/metadata/channel-map hashes, reserved segments, channel assignments, registration settings and supplied native displacement files. See the [complete interface and provenance documentation](../../docs/initial-evaluator-v1.md) for the JSON/NPZ contract and source details.

This package does not run native DREDge or establish authentic reproduction, human motion truth, protected assessment or scientific qualification. The rigid control and shared linear interpolation are distinct from the native online solver and default kriging interpolation. Metrics and inclusion/tolerance choices remain prospective; source declarations require external authentication. Current Dryad access, authentic geometry/preprocessing, full native cohort execution and rights gates remain open. Generated tests establish engineering behavior only.

## Authenticated input descriptors

The raw recording, SpikeGLX metadata, MATLAB channel map and displacement
archives are hashed and decoded through the same retained file descriptors.
Descriptor device/inode, size and modification/change times are checked before
and after hashing and decoding; a detected in-place mutation is refused before
a result is returned. This is a local file-integrity guard, not an immutable
filesystem or hostile-kernel guarantee. Returned segment arrays are detached
from the input mapping. The protocol receipt hashes the bytes actually parsed.

Five generated controls in `tests/test_verified_inputs.py` cover valid values,
a bad hash, pathname replacement, in-place mutation, protocol identity and
displacement replacement. No source recordings, native DREDge run, metric or
scientific qualification is added by this repair.
