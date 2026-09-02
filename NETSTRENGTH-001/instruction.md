# Strongest direct connections in the HCP group network matrix (NETSTRENGTH-001)

## Scientific context

The Human Connectome Project "MegaTrawls" release provides group-average resting-state
**network matrices** ("netmats") over a set of group-ICA nodes (Smith et al. 2013,
*Nature Neuroscience* 16:1852; methodology in Smith et al. 2011, *NeuroImage* 54:875,
"Network modelling methods for FMRI",
https://doi.org/10.1016/j.neuroimage.2010.08.063). A netmat summarises the functional
relationship between every pair of nodes, and identifying the strongest connections in
the group network is a standard way to describe the brain's dominant functional
architecture.

## Task

Using nilearn's pinned copy of the HCP MegaTrawls netmats
(`nilearn.datasets.fetch_megatrawls_netmats`) at the **d = 25** group-ICA dimensionality,
**identify the strongest direct functional connections in the group network matrix and
report them.**

The MegaTrawls d25 release ships two group-average network matrices over the same 25
nodes:

- **`Znet1`** — a full-correlation netmat (fetched with
  `matrices="full_correlation"`), amplitude-normalised and Fisher r-to-Z transformed.
- **`Znet2`** — a partial-correlation netmat (fetched with
  `matrices="partial_correlation"`), likewise r-to-Z transformed.

Both are 25 × 25, symmetric, with the diagonal undefined. Use the group-average
matrices (the fetcher returns the group netmat by default;
`timeseries="eigen_regression"`).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `strongest_connections.json` — a ranked list, strongest first, of the strongest direct
  connections you identify. Each entry gives the node pair as two node indices
  (e.g. `{"nodes": [i, j], "strength": <Z value>}`). List at least the top 5.
- `run_metadata.json` — dataset id, dimensionality, which matrix/matrices you used, and
  how you defined and ranked connection strength.
- `findings.md` — a short written summary naming the strongest direct connections (the
  node pairs) and explaining how you identified them. State only what your analysis
  actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `run_metadata.json`,
`strongest_connections.json`, and `findings.md`.
