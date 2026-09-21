# Network integration across participants: who has the most integrated brain? (NETINTEG-001)

## Scientific context

**Global efficiency** — the mean inverse shortest-path length of a network — is the standard
graph measure of functional-network **integration**: how readily information can move between
any two regions of the connectome (Latora & Marchiori, 2001; Rubinov & Sporns, 2010,
*NeuroImage*; Bullmore & Sporns, 2009). Comparing the integration of individual participants'
resting-state networks is a common way to relate brain organisation to cognition or diagnosis.

## Task

Using nilearn's ADHD-200 resting-state subset
(`nilearn.datasets.fetch_adhd(n_subjects=40)`), parcellate each participant's fMRI with the
**Schaefer-2018 100-region / 17-network** cortical atlas
(`nilearn.datasets.fetch_atlas_schaefer_2018(n_rois=100, yeo_networks=17, resolution_mm=2)`)
and form the parcel×parcel **Pearson correlation** connectome. For each participant, compute
the **global efficiency** of the functional connectome, then **rank the participants by
integration and identify which individuals have the most integrated brain networks.**

The standard construction choices the measure leaves to the analyst — nuisance regression and
temporal filtering, and how the correlation connectome is sparsified/thresholded and binarized
before the graph measure is computed — should follow common practice; the brief does not spell
them out.

Report, in plain terms, **the participant ranking and which participants are the most
integrated** — stating only what your analysis actually supports.

## Data

**Dataset:** ADHD-200 resting-state (nilearn `fetch_adhd`) + Schaefer-2018 atlas. Both are
downloaded programmatically at runtime by the loaders named above — nothing is pre-placed in
the container, so **internet access is required** on the first run (cached locally afterwards).
Participants are identified by the numeric subject id in each functional filename (e.g.
`0010042_rest_tshift_RPI_voreg_mni.nii.gz` → `10042`).

**Use exactly these 40 participants** (the set `fetch_adhd(n_subjects=40)` returns; pin them so
the cohort and ranking are reproducible), reported under their numeric ids: `10042`, `10064`,
`10128`, `21019`, `23008`, `23012`, `27011`, `27018`, `27034`, `27037`, `1019436`, `1206380`,
`1418396`, `1517058`, `1552181`, `1562298`, `1679142`, `2014113`, `2497695`, `2950754`,
`3007585`, `3154996`, `3205761`, `3520880`, `3624598`, `3699991`, `3884955`, `3902469`,
`3994098`, `4016887`, `4046678`, `4134561`, `4164316`, `4275075`, `6115230`, `7774305`,
`8409791`, `8697774`, `9744150`, `9750701`.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `efficiency.csv` — one row per participant: `participant, global_efficiency` (extra columns
  are welcome).
- `ranking.json` — the participants ordered most-to-least integrated, and the set of most
  integrated participants (`top_integrated`).
- `run_metadata.json` — dataset, number of participants, atlas, the method used, and an
  `integration_conclusion` field stating, in plain terms, what your ranking is.
- `findings.md` — a short written summary of the ranking and which participants are most
  integrated. State only what your analysis actually supports.

## Failure handling

If the dataset or the atlas cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write a parseable `run_metadata.json`, `efficiency.csv`, and
`findings.md`.
