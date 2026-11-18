# Immutable source reference for CI

The invocation test reads one upstream shell script as text. It never executes it. The existing test accepts an explicit `MINDBRIDGE_AUTHOR_SOURCE`; no workstation path is required. This reference is private CI/operator input and must not be included in candidate packets, including the `paper_data` arm.

`SOURCE_PROVIDER.json` identifies the author-hosted immutable provider, exact length and SHA256. The hosted page and raw rendering were observed, while the expected byte pin comes from the retained source cache. The complete retained tree has no license/notice file and the retained provenance reports no license. Consequently this proposal bundles no upstream source and infers no redistribution grant.

The integrator can provision the reference before the test using the following single-attempt recipe, from this component directory. `python3` means the explicitly selected CI interpreter. This recipe was statically reviewed, not executed in this phase. It uses the public author provider, with no credentials or branch fallback.

```sh
set -e
reference_root=$(mktemp -d "${RUNNER_TEMP:?}/mindbridge-reference.XXXXXX")
export MINDBRIDGE_AUTHOR_SOURCE="$reference_root"
python3 -I -B - <<'PY'
import hashlib, json, os, pathlib, urllib.request
provider = json.loads(pathlib.Path('SOURCE_PROVIDER.json').read_text())['provider']
with urllib.request.urlopen(provider['immutable_raw_url'], timeout=20) as response:
    body = response.read(provider['expected_bytes'] + 1)
if len(body) != provider['expected_bytes']:
    raise SystemExit('Source reference length mismatch')
if hashlib.sha256(body).hexdigest() != provider['expected_sha256']:
    raise SystemExit('Source reference hash mismatch')
destination = pathlib.Path(os.environ['MINDBRIDGE_AUTHOR_SOURCE']) / provider['relative_path']
destination.parent.mkdir(parents=True, exist_ok=True)
with destination.open('xb') as output:
    output.write(body)
PY
python3 -I -B test_invocation_manifest.py
```

Maximum response body read is832bytes including one length probe; successful retained payload is831bytes. Charge any failed/partial transfer and normal CI logs separately in the integrator's future execution budget, with a CI wall-time cap. No payload was acquired here. Cleanup is owned by the ephemeral CI workspace. This closes a concrete provider/path dependency; availability, future byte verification, CI adoption, and all model/data/scientific holds remain open. The13 accepted controls are not replayed by this delivery-only proposal.
