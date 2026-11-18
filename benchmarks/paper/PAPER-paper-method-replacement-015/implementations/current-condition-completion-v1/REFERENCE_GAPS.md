# Missing scientific reference inputs

The source-only audit authenticated all 18 supplied author-code/license files at
revision `1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f`. That supplied roster contains
neither the OASIS implementation/configuration nor the selected CASCADE model
configs and H5 checkpoint sets. This is a statement about the supplied assets,
not about whether those assets exist elsewhere.

For this current matched condition, each of four reference methods must produce
all 116 eligible recording vectors, including predictions for both neuron
cohorts. For class-specific spinal reference fits, exclude every recording of
the held neuron whenever it belongs to the training cohort. A class model trained
on that same held neuron cannot substitute for the required reference.

The supplied within-dataset demo does not implement this complete condition: it
selects `*_mini.mat`, uses noise levels 2/4/6/8, and does not preserve the original
recording boundaries in its prediction input. The current bank preserves all 44
neurons with the fixed noise-7/30-Hz/50-ms definition. Demo filename filters and
postprocessing cannot silently alter that definition.

Literal author training preallocates `X` with shape `(15000000, windowsize)` and
`Y` with shape `(15000000,)`, both float64. At a 64-bin window, this is
7,800,000,000 bytes before source data, copies, TensorFlow or models. It therefore
exceeds the existing 4 GiB participant profile. A larger trusted reference
runtime or a separately verified bounded equivalent is needed for that route.

The concrete next build is an operator-owned reference plan and per-record
inference/export adapter. It must bind exact configurations, the complete
checkpoint roster, all held-neuron training memberships, immutable source/data
identities, units and fixed support. CASCADE emits expected spikes per bin;
convert to Hz exactly once or declare the original units. Run each original
recording separately, preserve the fixed 32-bin margins, and refuse missing or
extra outputs. Missing model identities must stop reference production.

Source anchors in the pinned author roster are `cascade2p/utils.py:442-443`
(preallocation), `cascade2p/cascade.py:173-213` (training),
`cascade2p/cascade.py:609-733` (inference), and
`Demo scripts/Demo_benchmark_model_within_dataset.py:18-88` (demo differences).
`utils.py` SHA256 is
`0b9c9485d610e8de19c186bc0de9575509f358fedbe43b248b222a4ed91e0f63`;
`cascade.py` SHA256 is
`44579bba1dd7f28991b6ad24da39becf849c7d954d81ac3e00a9e8e728d587c5`.
The complete retained source-audit receipt is
`REFERENCE_RECIPE_GAP_MAP.json`, SHA256
`9acba758c8bc078937fe4e6663ff3439c02bee88d6de0bb5de2166d3c1e2abbc`.
No arrays or checkpoints were opened; no author modules were imported, network
calls made or models fitted. Historical Figure 4 equivalence remains unresolved.
