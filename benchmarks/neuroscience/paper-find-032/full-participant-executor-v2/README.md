# FIND032: complete paired participant executor

Task paper: [No evidence of neural feature-specific pre-activation during the prediction of an upcoming stimulus](https://www.nature.com/articles/s41467-026-73568-1), Nature Communications, 2026. This reanalysis uses the 2019 auditory MEG release.

The component implements **paper + data** versus **the same paper + data + approved official code**, with two complete-study programmes. It is an inactive source release, without an authentic scientific run or native qualification. It is not a ready Harbor task, validated benchmark result or new registration.

[COMPLETE_OPERATOR_API.md](COMPLETE_OPERATOR_API.md) is the operative guide. Retained earlier contracts saying the launcher/native owner is missing or Python3.9 is sufficient are superseded for software construction. **Use Python3.11+.** All20 external/scientific qualification gates remain open.

## Implemented scope

The real entry [`source/find032_runtime/operator_entry.py`](source/find032_runtime/operator_entry.py) captures authenticated source before imports. Its route includes the implemented operator, participant launcher, outer Linux owner, controller, Docker transport, staging, lifecycle, complete capture and target-last assessment. It constructs actual owner/registry/journal objects internally; there is no empty factory registry or missing controller to implement. Failures retain original execution state and block reference access.

Each arm uses all33 declared participants ×4 recordings:132 recordings,990 planned participant products,52 comparison dispositions, three BF10 dispositions, averaged random OOF confusion and six PDF figures. Only defined structural/theoretical-support unavailability is allowed. An endpoint option never permits dropping other available full-study outputs; see [output contract](contracts/CANDIDATE_OUTPUT_CONTRACT.md).

The profile is `corrected_methods_v1`, a disclosed methodological evaluation. Exact historical reproduction remains unavailable because original producer/version,135/141-axis and confusion/permutation joins are unresolved. Assessment returns numerical differences and figure byte identity, not a qualified binary reward, rendered figure verdict or frontier-improvement claim.

## Explicit external inputs

| Operand | Requirement |
|---|---|
| Study data | All132 admitted recordings from [release10.5281/zenodo.3268713](https://doi.org/10.5281/zenodo.3268713), with actual eligibility, trigger/channel/block/sample-clock semantics and rights independently checked. |
| Paper/official code | Authorized `paper`, `base`, `sound`, `omission`, `postprocessing`, `environment`, `readme` roles. Authenticate the selected bodies from [official repository](https://github.com/MEL-Eduwell-lab/predictive_activity). These participant materials are not omitted trusted evaluator modules. |
| Programmes | Pinned UTF8 A/B programmes, both frozen before recording views are staged; identical cohort, image, resources, seed and endpoint apart from code exposure. |
| Execution environment | Qualified Linux x86-64/root/cgroup-v2, Python/Docker executables/socket, existing pinned OCI image, storage/process ownership and explicit full budgets/deadlines. No environment/image installer is bundled. |
| Numerical environment | Qualified NumPy; full reference production additionally uses MNE, scikit-learn, SciPy, matplotlib, rpy2/R and BayesFactor0.9.12-4.6. Retained version selections are not an environment lock or qualification. |
| Protected reference | A competent full reference, exact result-manifest pin and independently justified tolerances. The substantive `find032.controller.reference_campaign` producer is included, but its authentic/native deployment is not supplied or automatically invoked. Supply a reference or separately qualify that producer's deployment. |

No old private verification directory, hidden answer archive, author workstation path or prior successful-run receipt is required. Current execution receipts cannot replace the actual owning objects. The private installer and its repository/census history are not public runtime dependencies.

## Prepare and invoke

Use the complete [field-by-field configuration guide](CONFIGURATION.md) and [four closed operand templates](CONFIGURATION_TEMPLATES.json). They include both native capacity ledgers, all132 input slots and all43 source rows. Unknown real paths, pins, resources and clocks are intentionally null; unfilled templates are rejected, not runnable examples. No private helper state is required.


1. Select the complete authentic protocol, host and resource envelope. No cheap subset or default compute request is supplied: the full reference has source-derived counts of111,672 fits and293,139 batch predictions before group work, not measured timing. Reserve candidate plus holder resources and both host input views as specified by the API.
2. Select a trusted control directory outside source/data/participant/reference roots. Create a root-bound map from all43 [SOURCE_GRAPH](SOURCE_GRAPH.json) rows. This example only prepares ordinary source metadata; it does not run the benchmark or issue trust:

```bash
python3.11 -I -S -B - /absolute/path/to/full-participant-executor-v2 /selected/control/runtime-sources.json <<'PY'
import hashlib, json, sys
from pathlib import Path
component = Path(sys.argv[1]).resolve(strict=True)
graph = json.loads((component / 'SOURCE_GRAPH.json').read_text())
assert graph['count'] == len(graph['files']) == 43
assert graph['bytes'] == sum(r['bytes'] for r in graph['files'].values()) == 431588
selection = {'schema': 'find032_captured_runtime_sources_v1',
             'root': str(component / 'source'), 'files': graph['files']}
body = (json.dumps(selection, sort_keys=True, indent=2) + '\n').encode()
with open(sys.argv[2], 'xb') as stream:
    stream.write(body)
print(json.dumps({'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}))
PY
```

Authenticate the checkout/graph, interpreter and entry in the enclosing trusted invocation. Keep ordinary source modes0644. The entry recaptures exact source bytes, rejects linked ancestry and preloaded project modules, and does not use ambient project bytecode. The example map is machine-specific; never reuse another host's absolute root or a partial graph.

3. Construct exact ordinary controller-config and operator-request JSON from COMPLETE_OPERATOR_API. The operator schema is `FIND032_COMPLETE_OPERATOR_V1`, with `schema`, `launch`, `assessment`, `budgets`, `numerical_search_roots`, `report_bytes`. Include complete132-input membership, seven exposure roles, both programmes, fixed image/resources/seed, normal/cleanup/**evidence** limits, attach-evidence cap and receipt-time reserve. Supply disjoint protected reference custody and explicit product/group tolerances. Library paths must be finite qualified runtime paths; there is no `.pth` processing or package installation.
4. After the complete execution is separately selected, use a fresh empty root-owned0550 cache and the actual fixed entry:

```text
<qualified-python-3.11+> -I -S -B -X pycache_prefix=<selected-empty-cache> \
  <component>/source/find032_runtime/operator_entry.py \
  --request <exact-operator-request> --request-bytes <N> --request-sha256 <sha256> \
  --source-manifest <root-bound-runtime-sources.json> \
  --source-manifest-bytes <N> --source-manifest-sha256 <sha256> \
  --original-endpoint <original-monotonic-assessment-end>
```

Preserve original streams, failures and terminal evidence; do not renew clocks or treat partial receipts as success. Both full candidates are admitted before the protected reference opens. Trusted callers can instead use implemented `execute_and_assess` through the same authenticated source/runtime route. No run was performed for this public projection.

## Source and rights

The original54 files remain exact:53 manifest payloads plus SOURCE_MANIFEST.json. All43 Python bodies, locks and contracts are unchanged. This README, CONFIGURATION.md and CONFIGURATION_TEMPLATES.json are three supplementary public files, outside that preserved manifest; no source loader imports them. The repository [MIT LICENSE](../../../../LICENSE) covers the project source. No article, official-code body, recording, protected reference, model weight or private installation proof is distributed here.

The upstream README's BSD-3-Clause statement has not been established as complete redistribution/dependency clearance. Separately establish rights for the article, data, official code and external dependencies; the project MIT notice does not grant them. The dormant inherited `CompositeCapacity`/`charged_directory` API references an absent supervision module and is unsupported; the selected concrete owner uses packaged Capacity and does not call it.
