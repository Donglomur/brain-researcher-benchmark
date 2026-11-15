# Retina construction primitives

Standard-library building blocks for constructing a neuroscience paper benchmark from [Nonlinear receptive fields evoke redundant retinal coding of natural scenes](https://doi.org/10.1038/s41586-024-08212-3). The component checks supplied manifests, field roles and coverage, computes limited protected scoring primitives, and validates byte transfers through an explicitly supplied response provider.

It includes 53 invented offline controls. It contains no retinal recordings, fitted answer parameters, authentic content manifest, upstream MATLAB implementation, or completed scientific reproduction.

## Run the offline controls

From the repository root on a Unix system with Python 3.11:

```sh
python -I -S -B components/retina-construction/run_offline_controls.py
```

The runner requires exactly 53 tests with no failures, errors, skips, expected failures or unexpected successes. Tests use fabricated records and temporary files containing invented bytes. All byte-transfer cases inject an offline response; no downloader is included. The workflow retains complete stdout, stderr and exit status.

The runner sets a 30-second alarm after standard-library imports, a 30/32-second soft/hard CPU limit, a 128 KiB per-file limit, a 64 KiB captured-log limit and a 128 KiB serialized-result limit. CI supplies a separate 40-second command deadline followed by up to five seconds of kill grace. There is no hard memory or hostile-code isolation boundary. These limits are for the offline controls, not a full scientific run.

## Library use

The three modules are adjacent, dependency-free Python modules. For example, from the component directory, this operates on invented vectors only:

```sh
cd components/retina-construction
python -S -B -c 'from scientific_kernels import score_response; print(score_response([0, 1, 2], [0, 1, 2]))'
```

| Function | Input and result |
|---|---|
| `retina_contract.validate_release_manifest` | Requires the exact 18 archive names, frozen DOI/commit and positive integer extents, content SHA-256 and metadata-evidence SHA-256 for every object. Returns a deterministic plan; declared digests do not authenticate their provenance. |
| `retina_contract.projection_plan` | Requires a complete declared 18-session member/field inventory. Classifies training fields, evaluation stimuli, protected responses and fitted answers; unknown or absent fields remain explicit. It does not decode MAT files or materialize a participant package. |
| `retina_contract.coverage_ledger` | Retains every declared unit, eligibility state and all six method outcomes. Counts exclusions, failures and historical omissions; matching published counts cannot verify the original population. |
| `scientific_kernels.score_response` | Requires aligned, complete finite target/prediction vectors. Returns SSE, MSE, unclipped R² and historical zero-clipped R² separately. Missing/NaN frames and overflow refuse; constant targets produce an explicit hold. |
| `scientific_kernels.pair_disagreement_ranking` | Requires both cells' SG and DoG predictions, protected test responses, and exhaustive fixation/nonfixation frame coverage. Returns the full range-normalized ranking; never applies an inferred top-20% cutoff or half partition. |
| `scientific_kernels.improvement_population_gate` | Checks complete supplied unit/error records but always withholds animal-balanced scores and improvement claims until an authenticated sampling hierarchy and population exist. |
| `archive_intake.acquire` | Validates and retains all 18 declared byte streams through a required response provider. No default transport, RAR extraction or MAT decoder is supplied. |

The invented fixtures in `test_retina_construction.py` demonstrate complete manifest, inventory and coverage schemas. Their toy extents, hashes, animal IDs and array values are not usable authentic metadata.

### Explicit byte provider

Call `acquire(manifest, output, wall_seconds, open_response)`. The output must be a new absolute directory with ordinary directory ancestors. The provider receives the fixed declared URL and remaining wall budget, and returns a context manager exposing:

- `status` equal to 200 and `geturl()` equal to the requested URL;
- `headers.get_all(name, default)` for content length, encoding and transfer framing;
- `read(n)` returning at most n bytes, with empty bytes marking EOF.

The primitive refuses redirected/status-mismatched responses, non-identity content encoding, duplicate/conflicting framing, short or oversized bodies, and digest mismatches. It creates exclusive private output files, retains completed objects and partial bytes, stops on the first failure without retry, and writes a receipt. A read exception leaves an explicit unknown-consumed-prefix flag. Provider/context/clock operations are not hard-isolated; a provider must honor its timeout and a separate outer owner must enforce the whole operation.

No authenticated content hashes or provider implementation are distributed here. A real intake requires independently authenticated metadata for the complete release, a reviewed provider and outer owner, adequate storage, and complete failure review. This helper alone does not make authentic acquisition ready.

## Full scientific scope stays required

The fixed release is [10.12751/g-node.ejk8kx](https://doi.org/10.12751/g-node.ejk8kx), at data commit `c177cb8fc7afbe74400f882856da8ad2a4bdcdf7`. The contract retains all 18 objects: 12 mouse recordings and six marmoset recordings. Archive filenames are not animal identities.

All eight cell types remain required: ON/OFF parasol, ON/OFF midget, transient-ON/OFF alpha and sustained-ON/OFF alpha. The declared Fig4 targets are 390 cells and 4,453 pairs; they are published reconstruction targets, not independently observed results. Fig4 and Fig5 require separate panel and pair membership reconstruction. Matching totals or supplying plausible animal IDs never authenticates a census or sampling hierarchy.

The complete intended endpoint remains Fig4 natural-movie prediction and correlation comparisons, Fig5 mechanistic decomposition, and the supporting STNMF/STClus comparisons in Extended Data 9–10. Required baselines remain white-noise LN, Gaussian-LN, DoG-LN, subunit grid (SG), STNMF and STClus. The original primary metrics and full denominators remain primary: historical clipped R², complete cell-type summaries, pair-correlation errors and the source-defined mechanistic comparisons. Unclipped R² is an additional diagnostic.

Failed fits, no-eligible-SG units and historically omitted STNMF parasol outcomes must remain visible. The public primitives implement only part of this endpoint: full pair scoring, exact historical eligibility/selection, population aggregation, all model/regularizer searches and independent numerical references are not implemented.

## Protected targets and assistance arms

Running-movie responses and admissible gratings can support training. Frozen-movie responses, mixed raw spike objects, fitted answer parameters and test-derived quantities remain protected. The field map is a plan over declarations; no physical read isolation or participant export has been established.

Three historical boundaries require particular care:

- Par45 uses frozen even/odd test-response reliability. This is scorer-only, not participant-visible eligibility evidence.
- Par84 divides SG–DoG prediction differences by each cell's **full frozen-test response range**, then averages over fixation frames and the pair. Nonfixation responses still contribute to that range. Zero range holds; ties and exact historical top-20% rounding remain unresolved.
- Par85 describes a separate half partition. The ranking function does not infer or implement that partition, fixation detection or panel lineage.

The proposed paper-plus-data and paper-plus-data-plus-code arms must share admissible training evidence, test stimuli and matched compute. The code arm may add a reviewed implementation-only snapshot of [the official code revision](https://github.com/dimokaramanlis/subunit_grid_model/tree/6b8a459f5693bd7820d23aff2e8950055ef64f47); fitted answer parameters remain excluded. Publishing these construction primitives does not supply either complete arm.

Any future improvement comparison needs a prospectively frozen complete population, training-only model selection/eligibility, fully tuned SG and DoG-LN baselines, all required original controls, full-test predictions and a justified inference plan. Candidate or baseline failures cannot disappear. Declared IDs do not unlock animal-balanced statistics or uncertainty estimates.

Authentic RAR/MAT decoding, stimulus/timing/RNG semantics, animal/session/panel joins, native dependencies, numerical parity, rights for redistributed data/code/helpers and public-data contamination remain separate unresolved requirements. No factual paper reproduction, LLM performance, SOTA result, completed benchmark or scientific qualification is established by these offline controls.
