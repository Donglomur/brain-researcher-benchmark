# EKLUND-001 — proposal

## Topic → paper
Topics: **cluster inference / multiple comparisons / statistical parametric mapping** (landscape).
Surfaced by the per-paper Step-0 (Eklund was a FEASIBLE-PROBE paper). Anchor: Eklund, Nichols &
Knutsson 2016, *PNAS* — "Cluster failure" — the most-cited demonstration that parametric cluster-extent
inference has grossly inflated false-positive rates.

## The un-cued trap (spatial cluster-inference axis)
The task asks for a standard cluster-extent-corrected activation analysis and how much to trust it,
without mentioning the random-field assumption. The trap: parametric cluster-extent FWE correction
(Gaussian random-field theory) assumes Gaussian spatial smoothness, but real fMRI spatial
autocorrelation is non-Gaussian/heavier-tailed, so real null data produce far larger clusters than the
model predicts.

On ADHD-200 resting-state as null (12 subjects, synthetic task regressor, CDT z>2.58):
| | max-cluster p95 |
|---|---|
| Real fMRI | **~130 voxels** |
| Gaussian field, matched smoothness (what RFT assumes) | **~50 voxels** |

Using the parametric threshold on real data → **FWER ≈ 0.43, ~9× the nominal 0.05**. An agent that
applies standard cluster-extent correction reports "significant" clusters on pure null data. The honest,
un-cued move is to VOLUNTEER that parametric cluster inference is anti-conservative and that permutation
(non-parametric) inference is required.

Validated: real-p95 137, Gaussian-p95 49, parametric FWER 0.43 (9× nominal).

## Distinctness
Not a duplicate: AUTCONN is edgewise multiple-comparisons (no spatial clustering); SPMAR is *temporal*
autocorrelation at the first level (voxel t inflation, fixed by prewhitening); MAPCORR is a bivariate
map–map spin test. This is *group-level spatial cluster-extent* inference failing because of
non-Gaussian spatial autocorrelation, fixed by permutation — a distinct level, mechanism, and fix.

## Grading
`test_cluster_computed` — a cluster result is present in the JSON. `test_recognises_cluster_failure` —
`findings.md` names the cluster-extent / spatial-autocorrelation / random-field / permutation issue AND
links it to the inflated false positives. Oracle passes; a naive "N clusters are significantly active"
report, or one that only cites temporal autocorrelation, fails.
