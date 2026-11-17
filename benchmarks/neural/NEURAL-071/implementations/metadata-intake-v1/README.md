# Narratives scan metadata intake

This executable intake joins the official subject manifest's independently ordered confound and left/right surface lists by BIDS person, task and run identity. It produces an operator scan inventory and reconciles participant task aliases against derivative membership and two available raw scan tables. No source list is assumed to share row order with another.

The existing programme accepts a caller-prepared release census. This component supplies the preceding authentic metadata join while preserving that programme and all historical source hashes. It does not supply the remaining story-family allocation, scan clocks or selected clean BOLD identities.

## Pinned inputs and usage

The accepted inputs are the retained [official subject metadata](https://github.com/snastase/narratives/blob/1736849ff80c80e1c73eda375ccf6497f5e234a9/subject_meta.json), [OpenNeuro participants](https://github.com/OpenNeuroDatasets/ds002345/blob/8a5af4022cdd78ed4263fc9b226c065e108bb24a/participants.tsv), and raw scan tables for [sub-278](https://github.com/OpenNeuroDatasets/ds002345/blob/8a5af4022cdd78ed4263fc9b226c065e108bb24a/sub-278/sub-278_scans.tsv) and [sub-280](https://github.com/OpenNeuroDatasets/ds002345/blob/8a5af4022cdd78ed4263fc9b226c065e108bb24a/sub-280/sub-280_scans.tsv). Exact body SHA-256 pins are enforced in `compile_inventory`; source acquisition is separate. Public upstream files are not bundled.

```sh
python intake.py --subject-meta SUBJECT_META_JSON --participants PARTICIPANTS_TSV \
  --sub-278-scans SUB_278_SCANS_TSV --sub-280-scans SUB_280_SCANS_TSV \
  --output EXTERNAL_OPERATOR_INVENTORY_JSON
```

Use the active resource-controlled test pool when executing in the parallel build. The CLI refuses to overwrite an existing output. Its standard output contains only counts; the detailed metadata inventory belongs outside Git and outside participant inputs. The inventory drops the upstream machine's absolute path prefix and retains source-relative derivative paths. It never opens any referenced recording path.

`join_inventory` is the reusable metadata transformation; `compile_inventory` authenticates the pinned snapshot before calling it. Duplicate JSON members, participants, confounds and hemispheres, missing hemisphere pairs, cross-person paths and incomplete participant coverage fail. Task-alias and raw membership disagreements remain explicit records rather than exclusions or repairs. Run entities remain distinct; absent run labels are not coerced to run 1.

## Scientific scope

The fixed source snapshot is the 345-person, 873-scan manifest used by the selected programme, rather than a claim to have recovered the descriptor's 891 scans. The fsaverage6 entries in this source are **fMRIPrep preprocessed** files. The programme's selected clean afni-nosmooth targets need their own authenticated source identities; preprocessed paths are not relabeled as clean data.

Task aliases are not story families. The compiler leaves `story_family` and `selected_clean_derivative` null and does not derive the 171-listener/486-case eligibility plan from task aliases. It retains both raw-verified and unverified scan memberships. The public metadata controls cannot qualify BOLD preparation, temporal alignment, atlas projection, predictive references or participant execution.

NEURAL-071 remains a neural-response prediction task. Frozen programme (F) and case investigation (I) require their distinct declared access paths; source intake and eventual programme scores do not establish direct or viewer-mediated neural interpretation. No private solver target, authentic recording, model or prediction is accessed by this component.

Run `test_intake.py` for generated controls covering shuffled lists, run identity, missing/duplicate hemispheres, duplicate confounds, person/pipeline mismatches, discrepancy retention, incomplete participants, source pins and deterministic output. These software controls establish metadata behavior, not neuroscience performance.
