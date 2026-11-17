# NEURAL-038 numerical investigation component

This component restores the six-component response arithmetic and numerical
scorer that the retained runtime manifest named but the repository did not
contain. It also supplies a complete public-export evaluator. It is an operator
component for the current sensory-context investigation, not a participant
transport or an admission of benchmark readiness.

`analysis_core.py`, `scorer_core.py`, and `delivery_io.py` are byte-identical
recoveries from the retained full140 investigation source. `evaluate.py` adds
strict 9/13/10/108 membership coverage, 300/300/300/200 frame dimensions,
condition/identity joins, metadata and array digest verification, bounded NPY
decoding, and independent recomputation from permitted public measurements.
It does not open a saved answer report. Use this wrapper for complete-task
evaluation; the recovered core scorer alone accepts other panel sizes.

## Scientific scope

For each original source membership, over zero-based half-open frames
`[125,128)`, the recovered algorithm computes:

| Field | Native-unit definition |
| --- | --- |
| `matched_increment` M | mean(vis1OptoF1 − visF1) |
| `unmatched_increment` U | mean(vis2OptoF1 − visF2) |
| `opto_only` O | mean(optoF1) |
| `context_interaction` | M − U |
| `matched_minus_opto` | M − O |
| `unmatched_minus_opto` | U − O |

Revision `matched`, `unmatched`, and `opto` traces are already incremental
responses. Their means use `[123,126)` without another visual subtraction.
All components use the same complete-window availability mask. NaNs within
any required window make the entire membership unavailable; NaNs outside
the window do not. Infinity anywhere in a delivered trace is invalid. No
zero imputation, smoothing, scaling, baseline adjustment, or deconvolution
is added.

The report contains every membership, six within-block means, the equally
weighted mean of the three original block interaction means, and the
revision mean interaction separately. With complete observations this is
866 scalar comparisons. A wholly unobserved block makes the complete score
unavailable. A partial missingness mask is preserved without replacing
unavailable components with numbers. The maximum scaled error is
`abs(actual − expected) / (1e-8 + 1e-6 * abs(expected))`; every required
number must have error at most one for numerical reconstruction.

Units remain the source fluorescence units. The author plot labels dF/F (%),
but this adapter performs no unit conversion. Native frame windows do not
establish a physical 120 ms interval. The opto-only residuals are descriptive
controls: missing baseline/context controls, optical artifacts and timing
matching prevent a stronger causal additivity claim. Original and revision
memberships do not establish distinct animals or independent cells.

## Operator use

Use Python 3.12 and the existing NumPy 2.2.6 environment specified by the
retained runtime. The public export contains `panel.json`, `input.json`, and
the eighteen condition NPY files named by `input.json`. Metadata digests
must come from an independently frozen operator source protocol, never from
the candidate submission. The CLI has no default source path or digest.

```sh
python evaluate.py \
  --public-root /operator/public-export \
  --panel-sha256 "$PANEL_SHA256" \
  --input-sha256 "$INPUT_SHA256" \
  --submission /operator/submission.json \
  --output /operator/new-score.json
```

The submission retains the recovered `neural038-investigation-v1` schema:
`schema`, `packet_id`, `blocks`, `original_macro_interaction`, and
`revision_mean_interaction`. Each block contains `block_id`, `cells`,
`valid_cells`, and `means`; each cell has `cell_key`, `availability`, and the
six fields above. Unavailable numeric values are JSON null. Missing, extra,
duplicate, nonfinite, and boolean operands are invalid. Candidate block and
cell ordering may vary; membership joins use identifiers.

The Python API accepts already authenticated metadata; the CLI supplies its
digest authentication. The output records numerical reconstruction only.
It makes no direct-observation, viewer, interactive-tool, frozen-program,
general-understanding, animal-inference, or scientific-success claim.

## Provenance and qualification

The primary source is [Zenodo record 18726362](https://zenodo.org/records/18726362),
archive `sequenceFiltering.zip`, MD5 `35b86a22f10b600dbd98f23db3f9343d`,
7,365,221,563 bytes; paper [10.1016/j.neuron.2025.12.024](https://doi.org/10.1016/j.neuron.2025.12.024).
The retained `Figure3_panelGI.ipynb.code.txt` was inspected directly: SHA-256
`52762797b52e4c401a7d896510fd13c6f2f2a8a706b5a03dc5c6e3fb2efc1acd`,
12,229 bytes. Its `calc_single_cells_resp` supplies the condition algebra,
original 9/13/10 declarations, revision 108×200 declaration and window offsets.
The separate block summaries and complete-case mask are retained benchmark
conventions, not a reproduction of the author's pooled statistical test.

Recovered source identities:

| File | SHA-256 |
| --- | --- |
| analysis_core.py | e75be729ca9a5f3df444b7b3441400c36af52013862b75f4eb946ed0651ed511 |
| scorer_core.py | 9cbfd7d824935274406c6e6e3a209c96934a57833939ebc3e79838fb2ccb436b |
| delivery_io.py | 9ba54409ff3aae8e17d2c0e96f1c5f335fa46cd33aeaf83d3be427a8ebf585d7 |

The recovered public export metadata was inspected without opening its
arrays: `input.json` SHA-256
`2a01997ce1f4e75049207ae09924229f560141bc48fba40a6644c5987c5310b2`,
6,506 bytes. It establishes the input adapter's field layout, source ROI
labels and original frame dimensions; it does not independently authenticate
the numeric payload or close historical source qualification.

`test_generated.py` contains generated software controls only, with a
closed-form fixture oracle independent of the restored trace arithmetic.
All 11 controls passed through the coordinated lightweight test pool on
2026-11-17 (Python 3.12, NumPy 2.2.6; 0.347252 child CPU seconds,
51,363,840 bytes peak child RSS). No authentic array
processing, historical private-answer read, model trial, source download,
biological qualification, or participant performance is part of this repair.
Source authorization, original/revision overlap, animal identity, physical
timing, optical-artifact checks, independent authentic recomputation and
participant delivery remain unresolved.
