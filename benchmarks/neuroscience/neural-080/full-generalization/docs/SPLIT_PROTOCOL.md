# NEURAL-080 crossed person and provenance-family split

This module implements the root-selected prospective split. It keeps the accepted
900 FIT / 100 validation / 102 exposed-query, within-person route as a separate
historical diagnostic. No assignment here claims a newly collected or exposure-free
study: source media overlap, training exposure, empirical provenance completeness,
and fresh-improvement custody must still be established by the actual operator.

## Required observed inputs

`ProvenanceGraph` contains exactly video IDs 1 through 1,102, one `VideoProvenance`
row per ID, all evidence-backed duplicate edges, a provider identity and source
version, and nonempty graph-level evidence. Each video row requires nonempty
`DonorIdentity(namespace, identity)` records and nonempty evidence descriptors.
Each duplicate edge requires two different selected IDs and nonempty evidence.
The separate person roster must contain all six canonical identities exactly once:
`sub-01` through `sub-06`. Every session and repeat of a selected person/video
coordinate remains in that coordinate; the splitter never selects repetitions.

Donor identities describe shared original source items or provenance, such as a
shared parent recording or original video identity. They are not analyst-created
semantic categories, task labels, arbitrary integer buckets, or a substitute for
missing provenance. Matching donor identities connect videos. Explicit observed
duplicate edges connect videos as well. Their transitive union defines a complete
component: a component can never be divided between folds. A generic collection
label that genuinely connects every video therefore produces one component and
fails the five-component requirement; it is not silently weakened.

An `EvidenceDescriptor` names a canonical relative path, observed positive byte
extent, and SHA-256. This module does not read, authenticate, infer, or approve the
referenced evidence. These fields preserve provider-supplied observations and their
provenance. Before evaluation, the genuine source-map owner must establish the
complete intended shared-provenance and duplicate graph. A syntactically valid
metadata graph or an assignment digest does not establish that empirical fact.
Absent evidence or source identities is an error, with no synthetic fallback.
An empty duplicate-edge tuple means the supplied graph contains no observed duplicate
edges; completeness of that claim remains an empirical source-review obligation.

## Deterministic five-fold assignment

`validate_graph` canonicalizes source metadata without changing observed values.
Video rows are ordered by ID; evidence is ordered by path, extent and hash; donor
identities are ordered by namespace and identity. Edge endpoints are sorted, edges
are ordered by endpoint pair, and repeated endpoint pairs are rejected rather than
silently discarding their evidence. Multiple evidence records for one pair belong
in the same edge.

`build_family_plan` computes connected components using shared donor identities
and all supplied duplicate edges. At least five real components are required.
For component member IDs sorted ascending, its tie key is SHA-256 of the UTF-8
bytes of `NEURAL080-family-v1`, one newline, then the compact JSON array of member
IDs, with no spaces. Components are considered in descending member count, breaking
ties by ascending hexadecimal tie key. Each whole component is allocated to the
fold with the smallest current video count, then the smallest fold index. Fold
indices are 0 through 4. All five folds must be nonempty. No fixed fold sizes or
family counts are invented; source-connected components determine those sizes.

The `FamilyPlan` retains the full canonical input graph, complete component member
lists and donor identities, every video's fold, and all five exact video-ID tuples.
The graph digest covers the complete canonical input graph. The assignment digest
covers the method, canonical person roster, graph digest, component allocation,
video-to-fold map, and fold member lists. Canonical serialization uses sorted JSON
object keys, compact separators, UTF-8 without ASCII escaping, and no NaN values.
`assignment_document` emits this complete data-only record. It contains no capability,
authentication-success flag, or authority issuer. `validate_family_plan` recomputes
component closure, allocation and both digests rather than trusting stored fields.

## Thirty outer cases and six hundred inner cells

`outer_cases(plan)` returns all six persons crossed with all five family folds,
in canonical person-then-fold order. Each `OuterCase` has:

- QUERY: the one held person crossed with every video in the held family fold.
- Outer training/selection universe: the other five persons crossed with all
  videos outside the held family fold.
- Exactly twenty inner validation cells: each of those five persons crossed
  with each of the four non-held family folds.

For an inner cell, validation is its one inner person crossed with the entire
inner family fold. Its FIT support contains only the four remaining persons and
only videos outside both the outer and inner family folds. It excludes the outer
person completely. Thus no response from either validation person or either held
family can enter that inner FIT transform, model fit, or preprocessing estimate.
After selection, a final outer fit may use only the complete outer training universe;
the outer query person and family remain excluded. All twenty inner cells are
required for selection, and all thirty outer cases are required for comparison.

The immutable `InnerCell` and `OuterCase` dataclasses carry exact person/video IDs.
Their coordinate iterators enumerate the complete cross products without loading
operands. Validators reject changed, missing, reordered or duplicated outer cases
and changed inner support. Every person/video coordinate occurs in exactly one
outer QUERY block, yielding all 6 x 1,102 queried coordinates across the thirty cases.
Unequal component/fold sizes remain explicit and must be respected by the selected
estimand; folds are not an extra biological replication count.

The splitter has no target, response, feature, accuracy, or calibration argument.
Graph construction, all assignments and source-review choices must be frozen before
query response access. Feature/target transforms and every tuning decision must
consume only the permitted FIT coordinates; the splitter supplies coordinates, not
permission to open data. Actual source/media/EEG/eye clock validity, matching of
rejected-trial support, protected comparison, resource enforcement, and empirical
reference competence remain responsibilities of the full programme.

## APIs and construction evidence

Public metadata APIs are `validate_graph`, `build_family_plan`,
`validate_family_plan`, `outer_cases`, `validate_outer_case`,
`validate_outer_cases`, `component_digest`, and `assignment_document`. The graph,
plan, component, inner-cell and outer-case objects are frozen dataclasses.

This authoring step wrote source and this protocol only. It parsed its source with
Python's AST parser. It did not execute the splitter, create invented split outputs,
read authentic metadata/data/media/headers, run controls, or import a numerical or
scientific package. Parent-owned engineering checks follow creator-source intake.
