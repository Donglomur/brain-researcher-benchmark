# Runtime source installation and remaining qualification

The runner accepts exactly `sha256:9aaf44dc64d85d0bbb0ffdd75ff5190ad94eff91d76849d14aea859c930955ff`, Linux ARM64. A matching local research image has installed-file provenance and a small generated native ABI check. No public registry object or redistributable image archive for that exact image is established. Full DMFC numerical and native isolation qualification on this image is still pending. See [FRESH_CHECKOUT.md](FRESH_CHECKOUT.md) for the usable source checks and data-provisioning route.

This package includes the complete eleven-file [runtime-context](runtime-context/SOURCE_LOCK.json): Dockerfile, dependency locks, two source licenses, artifact/version verifiers and default-deny Docker context filter. [RUNTIME_INSTALL_INPUTS.json](RUNTIME_INSTALL_INPUTS.json) pins every context file. The original context files are unchanged; their historical `artifacts_present:false` and `new_image_id:null` describe the source freeze, not later research-host observations. No wheel, image layer, scientific input or answer is bundled.

## Build from fixed public inputs

These commands are prospective operator-side installation instructions, not a claim that this publication executed a build. Use a fresh copy of `runtime-context` on a Linux ARM64 Docker/BuildKit host, with a finite resource allocation. Obtain precisely the seventeen wheels below; no dependency resolution or version substitution is intended. They total 84,435,444 compressed bytes. The complete verifier checks every length and SHA-256 before installation and rejects missing or extra files. The embedded lock also retains every immutable URL and hash.

From this package directory:

```sh
cd runtime-context
mkdir wheels
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 22228 --output wheels/cloudpickle-3.1.2-py3-none-any.whl \
  https://files.pythonhosted.org/packages/88/39/799be3f2f0f38cc727ee3b4f1445fe6d5e4133064ec2e4115069418a5bb6/cloudpickle-3.1.2-py3-none-any.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 4669544 --output wheels/h5py-3.13.0-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl \
  https://files.pythonhosted.org/packages/9e/d9/aed99e1c858dc698489f916eeb7c07513bc864885d28ab3689d572ba0ea0/h5py-3.13.0-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 7552 --output wheels/iniconfig-2.3.1-py3-none-any.whl \
  https://files.pythonhosted.org/packages/56/43/4ca9e49d27a1fcf6bece6f6aec0ea46bb9112489b93d4b688fb415457bdb/iniconfig-2.3.1-py3-none-any.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 306115 --output wheels/joblib-1.6.0-py3-none-any.whl \
  https://files.pythonhosted.org/packages/18/53/84099323c2ec4be98d935f63c033ac4151ee83836ca1050ede3b3aadf155/joblib-1.6.0-py3-none-any.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 14018462 --output wheels/numpy-2.2.6-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl \
  https://files.pythonhosted.org/packages/f8/35/8c80729f1ff76b3921d5c9487c7ac3de9b2a103b1cd05e905b3090513510/numpy-2.2.6-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 129956 --output wheels/packaging-26.3-py3-none-any.whl \
  https://files.pythonhosted.org/packages/63/34/ba1c580383c9eada3711951fef0795c80b829a078d72188184bcab9dd527/packaging-26.3-py3-none-any.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 15188645 --output wheels/pandas-2.2.3-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.whl \
  https://files.pythonhosted.org/packages/c6/2a/4bba3f03f7d07207481fed47f5b35f556c7441acddc368ec43d6643c5777/pandas-2.2.3-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 27082 --output wheels/pluggy-1.7.0-py3-none-any.whl \
  https://files.pythonhosted.org/packages/40/9e/2b38731e0fc536806f16490e1a12d7f0dc2a1235aa8cc07bcc75416a7daa/pluggy-1.7.0-py3-none-any.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 1250147 --output wheels/pygments-2.21.0-py3-none-any.whl \
  https://files.pythonhosted.org/packages/71/46/17f022dd3e953bf20a04a028a21ec746d942f8d2af30fa0f124fa0e6a684/pygments-2.21.0-py3-none-any.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 365474 --output wheels/pytest-8.4.1-py3-none-any.whl \
  https://files.pythonhosted.org/packages/29/16/c8a903f4c4dffe7a12843191437d7cd8e32751d5de349d45d3fe69544e87/pytest-8.4.1-py3-none-any.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 6837 --output wheels/pytest_json_ctrf-0.3.5-py3-none-any.whl \
  https://files.pythonhosted.org/packages/51/a8/d58637d10f70ae14a1ad18cb37f4aa32d5593510213d5f929892cb1c9c6d/pytest_json_ctrf-0.3.5-py3-none-any.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 92853 --output wheels/python_dateutil-4.0.0-py3-none-any.whl \
  https://files.pythonhosted.org/packages/2f/a9/52b89563d154433d79b51ed1eb4842bf7334cb2696891a7fe135618853d7/python_dateutil-4.0.0-py3-none-any.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 506321 --output wheels/pytz-2026.6-py2.py3-none-any.whl \
  https://files.pythonhosted.org/packages/b6/25/564f3fc5b70c1398d706c51f2b1470d0ea0b1b2f96fee67877b6f5bdf3b6/pytz-2026.6-py2.py3-none-any.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 12253728 --output wheels/scikit_learn-1.6.1-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl \
  https://files.pythonhosted.org/packages/a4/f6/ff7beaeb644bcad72bcfd5a03ff36d32ee4e53a8b29a639f11bcb65d06cd/scikit_learn-1.6.1-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 35210199 --output wheels/scipy-1.15.3-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl \
  https://files.pythonhosted.org/packages/56/30/a6f08f84ee5b7b28b4c597aca4cbe545535c39fe911845a96414700b64ba/scipy-1.15.3-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 32091 --output wheels/threadpoolctl-3.8.0-py3-none-any.whl \
  https://files.pythonhosted.org/packages/54/1b/831f2de4840a25db1dd7b1afea433ccafe6bb10aca07e13264f2079462d0/threadpoolctl-3.8.0-py3-none-any.whl
curl --fail --location --connect-timeout 15 --max-time 180 \
  --max-filesize 348210 --output wheels/tzdata-2026.6-py2.py3-none-any.whl \
  https://files.pythonhosted.org/packages/0a/66/9a06c2227fedfd4919f0eaaa8b94377d9730882a7e4f95823c9a331ab5e1/tzdata-2026.6-py2.py3-none-any.whl
python3 -I -S -B verify_artifacts.py --root wheels --lock WHEELS.json
```

The immutable base is `docker.io/library/python@sha256:608e6ed31df49009fa6c242fb61b5386a1c002e40c2b9cb1958e0f1041aaf06a`. [BASE_IMAGE.json](runtime-context/BASE_IMAGE.json) records Linux ARM64/v8, Python 3.12.8, configuration digest `sha256:70a416d0c62354c379ea7f473f5affd19f23c917adeb3a9c9b7ce39e6f97f3c9`, and four compressed layers totaling 44,933,770 bytes. Use the manifest digest, not a mutable Python tag or the configuration digest as a registry locator. The selected base and wheels total 129,369,214 compressed bytes, excluding metadata, decoded storage and Docker overhead. Historical planning reserved at least 8 GiB free disk and 6 GiB available host memory; this is not a new-machine measurement or an enforced Docker quota.

After complete wheel verification, the following obtains the fixed base and builds a **new local image** from the included source. The Dockerfile performs offline pip installation with required artifact hashes and runs `pip check` plus the declared-version checker. BuildKit support is required for `RUN --network=none`.

```sh
docker pull --platform linux/arm64 docker.io/library/python@sha256:608e6ed31df49009fa6c242fb61b5386a1c002e40c2b9cb1958e0f1041aaf06a
docker build --platform linux/arm64 --network=none --pull=false --no-cache \
  --tag dmfc-science:locked-source-v1 .
docker image inspect --format '{{.Id}}' dmfc-science:locked-source-v1
```

Record the actual returned image ID, platform, configuration, complete layer/history identities and installed software. A matching dependency lock does **not** guarantee that a fresh image has the existing `9aaf…` configuration digest. The build's version checker explicitly does not prove native ABI or scientific compatibility. The runner refuses another digest; do not edit guards or relabel an image to bypass that refusal. A different build identity needs its own reviewed explicit source profile and full finite qualification.

`--network=none` applies to build RUN steps; it is not a firewall for all daemon activity. The base acquisition above is explicitly networked. `--pull=false` alone does not prove that a missing base or layer cannot be resolved remotely. The immutable digest and complete identity checks are required even when a base is already present. This publication made no new network availability check and performed no image import, build or native run.

The original research build completed, then its post-build metadata guard refused Linux `ArgsEscaped:true`; a later field-specific completion accepted the exact existing image without rebuilding. That existing-image acceptance is not approval of a fresh digest. These public source commands are not a claim that the historical owner was a guaranteed single-command installer.

## Exact-image distribution and scientific checks

Transferring the exact existing image is a different route: audit configuration, full history and deleted-layer contents for private material, resolve redistribution notices, bind a published archive/registry identity to the accepted configuration and complete layers, and verify the destination import. No such public transfer artifact or destination verification is established. Installed-file provenance does not establish absence of private material in deleted layers.

The `pytest-json-ctrf` 0.3.5 wheel has an unresolved embedded-notice gap; its MIT metadata classifier alone is not complete notice clearance. The two included base-source licenses are not a substitute for the complete image's component notices. Public redistribution of the image is therefore not claimed cleared. This issue did not prevent the local research build.

Before describing this runner profile as ready for scientific use, preserve all 748 TRAIN trials, all 258 queries in each of four cells, both views/modes and all five fixed references. Compare all 1,032 predictions, ordered identities and complete metrics against the unchanged accepted evaluator-side outputs using a prospectively fixed tolerance. Preserve the original two-thread numerical environment; the tiny generic ABI check used one thread. Complete the relevant native isolation positives/negatives and verify producer termination, all four commitments before both public validations, then private grading. Do not refit historical references or silently change a cohort, tolerance, view or failure into a passing result. The package contains no private compatibility-output arrays.

The existing owner retains its 4,800-second complete-operation reservation (4,200 work plus 600 recovery), at most 46 numerical units, 900 seconds per cell, 120 seconds preparation and 4 GiB per cell. See [OPERATOR_ADMISSION.md](OPERATOR_ADMISSION.md) for the actual capacity/request contract. Source tests, runtime metadata and model/difficulty qualification remain distinct; no new benchmark ID, LLM result, SOTA claim or submission acceptance follows from building an image.
