# Unchanged author reference for generated differential controls

These files are copied without modification from [nerdslab/nuclr](https://github.com/nerdslab/nuclr/tree/0fa409b304147ace00507063d44f03155691af62), revision `0fa409b304147ace00507063d44f03155691af62`:

- `multi_split_eval.py`, originally `eval_scripts/multi_split_eval.py`, SHA256 `d7de1027643595308fd10daf8608d8d0ab466011ff80304f359ee7e44b5d4449`.
- `utils.py`, originally `eval_scripts/utils.py`, SHA256 `f813bc57f8de0c492f05a23e172f21a40e28e5b0663afe057a658d7f8dc79938`.
- The original `LICENSE`, retained here with the source.

Controls extract the exact functions needed for supplied-embedding readout. They do not run the author CLI, load models or start Ray. A synchronous test driver substitutes for Ray scheduling; numerical parity requires the actual pinned RandomOverSampler, StandardScaler and LogisticRegression dependencies. Local tests using explicit numerical doubles establish only the stated ordering/selection behavior. Historical paper-runtime identity is not claimed.
