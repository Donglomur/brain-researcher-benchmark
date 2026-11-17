# Human LFP alignment evaluator

Construction package for `PAPER-paper-method-add-003`: loads content-pinned raw SpikeGLX LFP segments, computes an independent rigid registration control, and compares supplied default-DREDge/alternate displacement outputs against fixed/no correction using shared interpolation, reserved evaluation channels and a prospective consistency/fidelity panel. Cohort summaries require Pt01, Pt02 and Pt03.

Dependencies: Python 3.11, NumPy and SciPy. The existing verified interpreter is `/opt/homebrew/opt/python@3.11/bin/python3.11`; no installation is required in the construction environment.

From this directory:

```sh
/opt/homebrew/opt/python@3.11/bin/python3.11 -m unittest discover -s tests -v
/opt/homebrew/opt/python@3.11/bin/python3.11 evaluator.py protocol.json results.json
```

The protocol provides explicit raw-file/metadata/channel-map hashes, reserved segments, channel assignments, registration settings and supplied native displacement files. See the [complete interface and provenance documentation](../../docs/initial-evaluator-v1.md) for the JSON/NPZ contract and source details.

This package does not run native DREDge or establish authentic reproduction, human motion truth, protected assessment or scientific qualification. The rigid control and shared linear interpolation are distinct from the native online solver and default kriging interpolation. Metrics and inclusion/tolerance choices remain prospective; source declarations require external authentication. Current Dryad access, authentic geometry/preprocessing, full native cohort execution and rights gates remain open. Generated tests establish engineering behavior only.
