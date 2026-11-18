# Structural identity sidecar construction

The retained NEURAL-032 preparation code has a recoverable identity projection:
`restricted_data.audit_dictionary` checks the dictionary's mouse, FOV and session
against the archive member name, then emits typed dendrite labels and namespaces
for each original row. The subsequent `project.py` export omits those fields.
Consequently, the flat investigation export does not demonstrate that the source
lacks this metadata. This component preserves the auditor's existing structural
output in a separate sidecar.

This is an operator helper with generated software controls. No authentic
sidecar has been created or validated. The 477396-byte historical observations,
their SHA-256, the paired-MAE component, primary estimand and readiness are
unchanged. Source hashes and the exact 27-member roster are recorded in
[SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json).

## Construction seam

In a separately reviewed execution of the existing trusted projection, retain
the already returned `checked` object immediately after its `audit_dictionary`
call. Do not decode the pickle again or load it directly with this helper:

```python
member_hierarchy = hierarchy.project_member(checked, member["index0"])
# After all 27 original members have been successfully audited:
sidecar = hierarchy.assemble(all_member_hierarchies)
```

The future operator must authenticate the complete original input closure and
the unchanged observation export. The helper's declared export hash is a binding
requirement; it does not authenticate the caller, source execution or input file.
There is intentionally no raw-data loader or execution CLI in this component.

`assemble` requires all 27 members, 1143 original rows and 20 mice. It checks
source paths, contiguous original row positions, typed labels and namespaces.
`join_rows(authenticated_observation_rows, sidecar)` requires an exact identity
join and returns separate `observation` and `hierarchy` objects. It preserves
every observation and leaves the existing scorer's row schema untouched. It does
not validate numeric observations in place of the existing source authenticator.

Only structural metadata enters the sidecar. Numeric volume, coactivity and
movement values are not copied. Missing dendrite labels remain explicit and
have no grouping namespace. Integer, string and floating-point labels remain
distinct, including their source types and floating-point bytes. Identical labels
from different mice, FOVs or sessions cannot merge into one group.

## Scientific limits

These are typed source labels, **not verified biological dendrite identities**.
The component does not establish anatomical branch correspondence, neighbor
geometry, measurement quality or stable longitudinal identity. It also cannot
establish that the recorded coactivity precedes followup, infer elapsed time from
the word `Early`, or justify exchangeability and matching rules. Missing labels
must not be converted to artificial dendrites or silently removed from support.
All compartments of an animal still belong to one mouse-level unit.

This recovers a construction path for metadata that the flat projection dropped.
The primary conditional-estimand schema, matching, multiplicity policy, trusted
numerical grader, complete participant transports and authentic execution remain
separate unfinished requirements. There is no direct neural-understanding,
prediction improvement, causal or paper-reproduction result.

## Verification and integration

Run `python3 -I -S -B test_hierarchy.py` in this directory for generated controls.
They exercise omitted measurements, complete-member joins, missing labels,
namespace separation, typed token distinctions, forged missing states, malformed
identities, and bool/float substitutions in integer metadata. Generated per-member
row counts are expressly not observations of the original data.

The proposed new component needs an explicit CI command enrollment at its public
destination; adding files alone does not activate the existing component runner.
It does not change the task, understanding contract, existing runtime manifest,
central authority files or current benchmark counts.
