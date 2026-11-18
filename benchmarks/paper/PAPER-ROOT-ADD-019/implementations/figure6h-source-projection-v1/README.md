# Figure 6h source input projection

This component covers a preparation seam between a future authenticated native
export and the existing Figure 6h OOF scorer. It does not read MAT files, recover
the original cohort, calculate quartiles, create folds, fit models or qualify a
reproduction/improvement result. The original task remains source unresolved.

The [pinned author decoder](https://github.com/constantinoplelab/published/blob/b7b68ca8c107d8ce4a061e16da214307f175c3e5/DMS_AChDA/vis/plot_fig6h.m)
selects time indices using the first unit's SON grid, applies those indices to
every unit, and reshapes a trial-by-unit-by-time tensor in MATLAB column-major
order. The resulting predictor order varies units within each time point.
Ordinary row-major flattening changes that input. The nearest-grid endpoint can
also differ from the nominal 0 or 0.5 seconds; ties retain the first index.

`project_session(record)` checks a neutral, operator-owned source export and
returns the selected trial-by-predictor matrix, explicit feature coordinates,
retained trial/unit order and the existing scorer's literal-label audit. It
refuses mismatched unit clocks, row identities, malformed geometry or nonfinite
selected predictors. It never resamples or drops rows. Nonfinite values outside
the selected trials/window do not affect the matrix. Clock/geometry checks are
explicit admission guards: failure requires source adjudication, not a claim
that the author code could not have run.

Captured masks and labels are mandatory. The function preserves the source's
sequential label mutation, reports collisions and inclusive-quartile overlap,
and marks a resulting single-class selection. It does not choose corrected
labels, outlier filtering or percentile semantics. Source-export hashes bind
an external native-export artifact, not the neutral record containing the hash;
their authenticity and the export-to-record mapping need separate verification.

`project_complete_panel(panel)` requires all eighteen declared sessions, eight
rat IDs, and the original increasing session-index order. These are consistency
checks, not authentication of the original cohort. A single-session output is
only a component result and cannot replace the complete panel.

`test_project.py::fixture` documents the exact input wire format with invented
values. The whole return object, including audit labels and source identities,
is **operator private**. A participant projection, delivery boundary and native
exporter are not supplied. Source example traces, original folds and all eleven
native prediction/loss records remain separate missing requirements.

The existing sibling `figure6h-oof-score-v1/score.py` is a pinned dependency; its
reviewed label-audit routine is reused without modification. Generated controls
cover hand-derived predictor order, nearest-index ties, irrelevant-sample
invariance, mismatched clocks/rows, literal label collisions, overlapping masks,
full-panel support and malformed inputs. Run through the project's shared
two-slot test pool with `python3 -I -S -B test_project.py`; no authentic inputs
or scientific fits are used. New component CI enrollment is still required.
